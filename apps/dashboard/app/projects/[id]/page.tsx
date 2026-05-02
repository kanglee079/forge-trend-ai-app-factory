import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { ProjectDetailClient } from "./ProjectDetailClient";

export default async function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const project = await api.project(id).catch(() => null);
  if (!project) notFound();
  return <ProjectDetailClient initialProject={project} />;
}
