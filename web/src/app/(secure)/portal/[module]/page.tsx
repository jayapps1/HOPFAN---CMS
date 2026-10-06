import { notFound } from "next/navigation";
import { modules } from "@/lib/permissions";
import { ModuleWorkspace } from "@/features/dashboard/module-workspace";
export default async function ModulePage({ params }: { params: Promise<{ module: string }> }) {
  const { module: id } = await params; const module = modules.find(item => item.id === id);
  if (!module) notFound();
  return <ModuleWorkspace moduleId={module.id} />;
}
