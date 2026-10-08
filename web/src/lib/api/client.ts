import { parseCsrf, parseLogin, parseUser } from "./contracts";
import type { CsrfResponse, CurrentUser, LoginMethod } from "@/types/auth";

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string, public readonly retryAfter?: number) {
    super(message); this.name = "ApiError";
  }
}
const messages: Record<string, string> = {
  AUTHENTICATION_REQUIRED: "Your session expired. Please sign in again.",
  PASSWORD_CHANGE_REQUIRED: "Change your temporary password in the HOPFAN desktop app, then sign in here.",
  CSRF_INVALID: "Please refresh the sign-in page and try again.",
  ORIGIN_NOT_ALLOWED: "Sign-in is unavailable from this address. Contact your church administrator.",
  ACCESS_DENIED: "You do not have permission to access this area.",
  RATE_LIMITED: "Too many attempts. Please wait before trying again.",
  DATABASE_UNAVAILABLE: "HOPFAN is temporarily unavailable. Please try again shortly.",
  VALIDATION_ERROR: "Check your details and try again.",
  RESOURCE_NOT_FOUND: "This record is unavailable.",
  OPERATION_CONFLICT: "This record changed or already exists. Refresh and try again.",
  BUSINESS_RULE_VIOLATION: "This operation is unavailable in the current state. Check the fields and refresh.",
  PAYMENT_UNAVAILABLE: "Online checkout is temporarily unavailable. Please contact the church or try again later.",
  PAYMENT_UNCONFIRMED: "We couldn’t confirm this payment. Please contact the church with your reference.",
  CHECKOUT_PENDING: "Checkout is still being prepared. Please wait, then try again.",
  ATTEMPT_CONFLICT: "Start a new donation for changed details.",
};
interface RequestOptions { method?: "GET" | "POST" | "PATCH"; body?: unknown; authenticated?: boolean; csrf?: boolean; loginMethod?: LoginMethod; signal?: AbortSignal; responseType?: "text"; credentials?:RequestCredentials; headers?:Record<string,string> }

export class ApiClient {
  private csrfToken: string | null = null;
  private csrfRequest: Promise<CsrfResponse> | null = null;
  private meRequest: Promise<CurrentUser> | null = null;
  private unauthorized = new Set<() => void>();
  constructor(private readonly baseUrl: string, private readonly fetcher: typeof fetch = (...args) => fetch(...args), private readonly timeout = 15_000) {}

  onUnauthorized(listener: () => void): () => void {
    this.unauthorized.add(listener);
    return () => { this.unauthorized.delete(listener); };
  }
  clearSession(): void { this.csrfToken = null; }

  private async request(path: string, options: RequestOptions = {}, retried = false): Promise<unknown> {
    if (options.csrf && !this.csrfToken) await this.csrf();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    let response: Response;
    let data: unknown;
    try {
      response = await this.fetcher(`${this.baseUrl}${path}`, {
        method: options.method ?? "GET", credentials: options.credentials ?? "include", cache: "no-store",
        signal: options.signal ? AbortSignal.any([controller.signal, options.signal]) : controller.signal,
        headers: { Accept: "application/json", ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
                   ...(options.csrf ? { "X-CSRF-Token": this.csrfToken ?? "" } : {}),...options.headers },
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      });
      try { data = response.ok && options.responseType === "text" ? await response.text() : await response.json(); }
      catch { if (controller.signal.aborted) throw new Error("Request timed out"); data = null; }
    } catch {
      if (controller.signal.aborted && !options.signal?.aborted)
        throw new ApiError(0, "REQUEST_TIMEOUT", "HOPFAN took too long to respond. Please try again.");
      throw new ApiError(0, "NETWORK_ERROR", "Unable to reach HOPFAN right now. Confirm the server is running and try again.");
    } finally { clearTimeout(timer); }
    if (!response.ok) {
      const details = typeof data === "object" && data !== null && "error" in data ? (data as { error: unknown }).error : null;
      const rawCode = typeof details === "object" && details !== null && "code" in details ? (details as { code: unknown }).code : null;
      const code = typeof rawCode === "string" && /^[A-Z_]{1,64}$/.test(rawCode) ? rawCode : "REQUEST_FAILED";
      if (code === "CSRF_INVALID" && options.csrf && !retried) {
        await this.csrf(); return this.request(path, options, true);
      }
      if (response.status === 401 && options.authenticated) {
        this.clearSession(); this.unauthorized.forEach(listener => listener());
      }
      const message = code === "INVALID_CREDENTIALS"
        ? options.loginMethod === "totp" ? "Invalid authenticator code." : "Invalid email or password."
        : messages[code] ?? (response.status >= 500 ? "HOPFAN encountered a server error. Please try again." : "Unable to complete this request. Please try again.");
      const retry = Number(response.headers.get("Retry-After"));
      throw new ApiError(response.status, code, message, retry > 0 ? retry : undefined);
    }
    return data;
  }
  private parse<T>(data: unknown, decoder: (value: unknown) => T): T {
    try { return decoder(data); } catch { throw new ApiError(0, "INVALID_RESPONSE", "HOPFAN returned an unexpected response. Please try again."); }
  }
  async get<T>(path: string, decoder: (value: unknown) => T, signal?: AbortSignal): Promise<T> {
    if (!path.startsWith("/api/v1/")) throw new Error("Invalid API resource");
    return this.parse(await this.request(path, { authenticated: true, signal }), decoder);
  }
  async connectivity(): Promise<boolean> {
    try {
      const response = await this.fetcher(this.baseUrl + "/api/v1/health", {
        credentials: "omit", cache: "no-store", signal: AbortSignal.timeout(3000),
      });
      const data: unknown = await response.json();
      return response.ok && typeof data === "object" && data !== null && "status" in data && data.status === "ok";
    } catch { return false; }
  }
  assetUrl(path: string): string {
    if (!/^\/api\/v1\/(?:public\/media\/[a-f0-9-]{36}|website\/media\/[a-f0-9-]{36}\/preview)(?:\?size=(?:320|960|1920))?$/.test(path)) return "";
    return this.baseUrl + path;
  }
  photoUrl(path: string): string {
    if (!/^\/api\/v1\/(?:media\/member-photo\/[a-f0-9-]{36}|(?:attendance|sunday-school\/attendance)\/sessions\/[a-f0-9-]{36}\/photo\/[a-f0-9-]{36})$/.test(path)) return "";
    return this.baseUrl + path;
  }
  async mutate<T>(path: string, body: unknown, decoder: (value: unknown) => T, method: "POST" | "PATCH" = "POST"): Promise<T> {
    if (!path.startsWith("/api/v1/")) throw new Error("Invalid API resource");
    return this.parse(await this.request(path, { method, body, authenticated: true, csrf: true }), decoder);
  }
  sermonMediaUrl(path:string):string{
    if(!/^\/api\/v1\/(?:sermons\/[a-f0-9-]{36}\/media\/[a-f0-9-]{36}\/preview|public\/sermons\/[a-z0-9-]+\/(?:media\/[a-f0-9-]{36}|download\/[a-z]+))$/.test(path))return '';
    return this.baseUrl+path;
  }
  async uploadSermon(path:string,file:File,kind:string,rights:boolean,download:boolean,onProgress:(percent:number)=>void,signal:AbortSignal):Promise<unknown>{
    if(!/^\/api\/v1\/sermons\/[a-f0-9-]{36}\/media$/.test(path))throw new Error('Invalid media upload');
    const csrf=await this.csrf();
    return new Promise((resolve,reject)=>{
      const request=new XMLHttpRequest();const query=new URLSearchParams({filename:file.name,media_type:kind,rights_attested:String(rights),download_allowed:String(download)});
      request.open('POST',this.baseUrl+path+'?'+query);request.withCredentials=true;request.responseType='json';request.timeout=30*60*1000;
      request.setRequestHeader('Content-Type',file.type||'application/octet-stream');request.setRequestHeader('X-CSRF-Token',csrf.csrf_token);
      request.upload.onprogress=event=>{if(event.lengthComputable)onProgress(Math.round(event.loaded/event.total*100));};
      const abort=()=>request.abort();signal.addEventListener('abort',abort,{once:true});
      const done=()=>signal.removeEventListener('abort',abort);
      request.onerror=()=>{done();reject(new ApiError(0,'NETWORK_ERROR','Upload failed. Check the connection and try again.'));};
      request.ontimeout=()=>{done();reject(new ApiError(0,'UPLOAD_TIMEOUT','Upload timed out. Please try again.'));};
      request.onabort=()=>{done();reject(new ApiError(0,'UPLOAD_CANCELLED','Upload cancelled.'));};
      request.onload=()=>{done();if(request.status===202)resolve(request.response);else reject(new ApiError(request.status,'UPLOAD_FAILED',request.status===413?'This file exceeds the configured upload limit.':request.status===403?'You do not have upload permission.':'The upload could not be accepted. Check the file type and authorization.'));};
      if(signal.aborted){done();reject(new ApiError(0,'UPLOAD_CANCELLED','Upload cancelled.'));return;}request.send(file);
    });
  }
  async publicMutation<T>(path:string,body:unknown,decoder:(value:unknown)=>T):Promise<T>{
    if(!path.startsWith('/api/v1/public/'))throw new Error('Invalid public resource');
    return this.parse(await this.request(path,{method:'POST',body,credentials:'omit',authenticated:false}),decoder);
  }
  async publicGet<T>(path:string,decoder:(value:unknown)=>T,token?:string):Promise<T>{
    if(!path.startsWith('/api/v1/public/'))throw new Error('Invalid public resource');
    return this.parse(await this.request(path,{credentials:'omit',authenticated:false,headers:token?{'X-Donation-Token':token}:undefined}),decoder);
  }
  async csv(path: string): Promise<string> {
    if (!path.startsWith("/api/v1/")) throw new Error("Invalid API resource");
    return this.parse(await this.request(path, { authenticated: true, responseType: "text" }), value => {
      if (typeof value !== "string") throw new Error();
      return value;
    });
  }
  csrf(): Promise<CsrfResponse> {
    if (!this.csrfRequest) {
      this.csrfRequest = this.request("/api/v1/auth/csrf").then(data => {
        const result = this.parse(data, parseCsrf); this.csrfToken = result.csrf_token; return result;
      }).finally(() => { this.csrfRequest = null; });
    }
    return this.csrfRequest;
  }
  currentUser(): Promise<CurrentUser> {
    if (!this.meRequest) this.meRequest = this.request("/api/v1/me", { authenticated: true })
      .then(data => this.parse(data, parseUser)).finally(() => { this.meRequest = null; });
    return this.meRequest;
  }
  async login(method: LoginMethod, email: string, credential: string): Promise<CurrentUser> {
    const result = this.parse(await this.request(`/api/v1/auth/${method}-login`, {
      method: "POST", body: { email, [method === "password" ? "password" : "code"]: credential }, csrf: true, loginMethod: method,
    }), parseLogin);
    this.csrfToken = result.csrf_token;
    return this.currentUser();
  }
  async logout(): Promise<void> {
    try { await this.request("/api/v1/auth/logout", { method: "POST", authenticated: true, csrf: true }); }
    catch (error) { if (!(error instanceof ApiError && error.status === 401)) throw error; }
    this.clearSession();
  }
}

function configuredOrigin(value: string): string {
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password ||
        !["", "/"].includes(url.pathname) || url.search || url.hash) throw new Error();
    if (process.env.NODE_ENV === "production" && url.protocol !== "https:" &&
        !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) throw new Error();
    return url.origin;
  } catch { throw new Error("The portal API origin must be a valid HTTP(S) origin without credentials or a path."); }
}
export const api = new ApiClient(configuredOrigin(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"));
