import { request } from "@playwright/test";
export default async function teardown() {
  const api = await request.newContext();
  try { await api.post("http://localhost:8001/_test/cleanup"); }
  finally { await api.dispose(); }
}
