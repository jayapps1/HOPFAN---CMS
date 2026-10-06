"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Card, Button } from "@/components/ui/primitives";
import { ErrorMessage } from "@/components/ui/feedback";
import { type Stats, statusLabel } from "@/lib/api/operations";
export function OperationalModal({ title,description,children,close }: {title:string;description:string;children:ReactNode;close:()=>void}) {
  return <Dialog.Root open onOpenChange={open=>{if(!open)close();}}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content operational-dialog">
    <Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description>{children}
    <Dialog.Close className="dialog-close" aria-label="Close dialog"><X size={19}/></Dialog.Close></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
export function SummaryCards({ stats }: {stats:Stats}) {
  return <div className="attendance-summary" aria-label="Attendance summary">{(["eligible","present","late","excused","absent","unmarked"] as const).map(key=><Card key={key}><p>{key==="eligible"?"Total roster":statusLabel(key)}</p><strong>{stats[key]}</strong></Card>)}
    <Card><p>Attendance rate</p><strong>{stats.rate===null?"Unavailable":stats.rate+"%"}</strong></Card></div>;
}
export function FormActions({ pending,error,close,label="Save" }: {pending:boolean;error:string;close:()=>void;label?:string}) {
  return <>{error&&<ErrorMessage message={error}/>}<div className="form-actions"><Button type="button" variant="secondary" disabled={pending} onClick={close}>Cancel</Button><Button type="submit" pending={pending}>{pending?"Saving…":label}</Button></div></>;
}
