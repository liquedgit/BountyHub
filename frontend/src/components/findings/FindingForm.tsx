"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Markdown } from "@/components/common/Markdown";
import {
  FINDING_STATUSES, SEVERITIES, type Finding, type FindingStatus, type Severity, type Target,
} from "@/lib/types";
import { parsePayout, payoutToInput } from "./payout";

export interface FindingValues {
  title: string;
  description: string | null;
  severity: Severity;
  status: FindingStatus;
  target_id: number | null;
  payout_cents: number | null;
}

export function FindingForm({
  finding,
  targets,
  pending,
  error,
  submitLabel,
  onSubmit,
  extraActions,
}: {
  finding?: Finding;
  targets: Target[];
  pending: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: (values: FindingValues) => void;
  extraActions?: React.ReactNode;
}) {
  const [title, setTitle] = useState(finding?.title ?? "");
  const [description, setDescription] = useState(finding?.description ?? "");
  const [severity, setSeverity] = useState<Severity>(finding?.severity ?? "info");
  const [status, setStatus] = useState<FindingStatus>(finding?.status ?? "new");
  const [targetId, setTargetId] = useState<string>(finding?.target_id != null ? String(finding.target_id) : "");
  const [payout, setPayout] = useState(payoutToInput(finding?.payout_cents ?? null));
  const [touched, setTouched] = useState(false);

  const parsed = parsePayout(payout);
  const titleError = title.trim() ? null : "Title is required.";

  return (
    <form
      className="space-y-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setTouched(true);
        if (titleError || parsed.error) return;
        onSubmit({
          title: title.trim(),
          description: description.trim() ? description : null,
          severity,
          status,
          target_id: targetId ? Number(targetId) : null,
          payout_cents: parsed.cents,
        });
      }}
    >
      <div className="space-y-1.5">
        <Label htmlFor="finding-title">Title</Label>
        <Input id="finding-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} />
        {touched && titleError ? <p className="text-xs text-destructive">{titleError}</p> : null}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="finding-severity">Severity</Label>
          <Select id="finding-severity" value={severity} onChange={(e) => setSeverity(e.target.value as Severity)}>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="finding-status">Status</Label>
          <Select id="finding-status" value={status} onChange={(e) => setStatus(e.target.value as FindingStatus)}>
            {FINDING_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="finding-target">Target</Label>
          <Select id="finding-target" value={targetId} onChange={(e) => setTargetId(e.target.value)}>
            <option value="">No target</option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>{t.value}</option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="finding-payout">Payout (USD)</Label>
          <Input
            id="finding-payout"
            inputMode="decimal"
            placeholder="0.00"
            value={payout}
            onChange={(e) => setPayout(e.target.value)}
            aria-invalid={parsed.error ? true : undefined}
          />
          {parsed.error ? <p className="text-xs text-destructive">{parsed.error}</p> : null}
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="finding-description">Description (markdown)</Label>
        <Textarea
          id="finding-description"
          className="min-h-32 font-mono"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        {description.trim() ? (
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground">Preview</summary>
            <Markdown className="mt-2 rounded-md border p-3">{description}</Markdown>
          </details>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="text-sm text-destructive">{error}</p>
      ) : null}
      <DialogFooter className="sm:justify-between">
        <div>{extraActions}</div>
        <Button type="submit" disabled={pending}>
          {pending ? "Saving…" : submitLabel}
        </Button>
      </DialogFooter>
    </form>
  );
}
