import { useEffect, useId, useRef } from "react";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Input } from "../../components/Input";
import { Select } from "../../components/Select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/Table";
import type { GuideScene } from "./types";

export function GuidePreview({ scene, description, zoom = false }: { scene: GuideScene; description: string; zoom?: boolean }) {
  const content = useRef<HTMLDivElement>(null);
  const prefix = useId();
  useEffect(() => { content.current?.setAttribute("inert", ""); }, []);
  return <div role="img" aria-label={description} className="@container" data-guide-preview>
    <div ref={content} aria-hidden="true" className="bg-slate-50 p-3 @md:p-5 pointer-events-none select-none">
      <Card className="overflow-hidden">
        <div className="border-b border-slate-200 px-4 py-3 bg-white">
          <p className={`${zoom ? "text-xl" : "text-base"} font-semibold text-slate-900`}>{scene.title}</p>
          {scene.subtitle && <p className="mt-1 text-xs text-slate-500">{scene.subtitle}</p>}
        </div>
        <div className="p-4 space-y-5">
          {scene.regions.map((region, index) => <div key={index} className="relative rounded-xl border border-blue-100 bg-white p-3 pt-4">
            <span data-guide-marker={index + 1} className="absolute -top-3 left-3 h-6 w-6 rounded-full bg-blue-600 ring-2 ring-white text-white text-xs font-bold grid place-items-center shadow-xs">{index + 1}</span>
            {region.title && <p className="text-sm font-semibold mb-3">{region.title}</p>}
            {region.fields && <div className="grid @md:grid-cols-2 gap-3">
              {region.fields.map((field, fieldIndex) => field.options ?
                <Select key={fieldIndex} id={`${prefix}-${index}-${fieldIndex}`} label={field.label}
                  className={zoom ? "text-base!" : ""}
                  value={field.value || field.options[0]} onChange={() => {}} tabIndex={-1}
                  options={field.options.map((label) => ({ value: label, label }))} /> :
                <Input key={fieldIndex} id={`${prefix}-${index}-${fieldIndex}`} label={field.label}
                  className={zoom ? "text-base!" : ""}
                  type={field.type || "text"} value={field.value || ""} placeholder={field.placeholder}
                  readOnly tabIndex={-1} />)}
            </div>}
            {region.stats && <div className="grid grid-cols-2 @lg:grid-cols-4 gap-3">
              {region.stats.map((stat) => <div key={stat.label} className="rounded-lg bg-blue-50 p-3">
                <p className="text-xs text-slate-500">{stat.label}</p><p className="mt-1 text-xl font-semibold text-slate-900">{stat.value}</p>
              </div>)}
            </div>}
            {region.table && <Table><TableHeader><TableRow>{region.table.columns.map((label) => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader>
              <TableBody>{region.table.rows.map((row, rowIndex) => <TableRow key={rowIndex}>{row.map((value, column) => <TableCell key={column} className={`${zoom ? "text-base" : "text-xs"} whitespace-nowrap`}>{value}</TableCell>)}</TableRow>)}</TableBody>
            </Table>}
            {region.badges && <div className="flex flex-wrap gap-2 mt-2">{region.badges.map((label) => <Badge key={label} variant="info">{label}</Badge>)}</div>}
            {region.note && <p className={`rounded-lg bg-slate-50 p-3 ${zoom ? "text-base" : "text-xs"} leading-6 text-slate-600 mt-2`}>{region.note}</p>}
            {region.buttons && <div className="flex flex-wrap gap-2 mt-3">{region.buttons.map((label, buttonIndex) =>
              <Button key={label} type="button" tabIndex={-1} size={zoom ? "md" : "sm"} className={zoom ? "text-base!" : ""} variant={buttonIndex ? "outline" : "primary"}>{label}</Button>)}</div>}
          </div>)}
        </div>
      </Card>
    </div>
  </div>;
}
