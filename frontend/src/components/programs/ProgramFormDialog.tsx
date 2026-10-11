"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errorMessage } from "@/lib/api";
import type { Program } from "@/lib/types";

/** Create (no `program`) or edit (with `program`) dialog. */
export function ProgramFormDialog({
  open,
  onOpenChange,
  program,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  program?: Program;
  onSaved?: (program: Program) => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState("");
  const [url, setUrl] = useState("");
  const [reward, setReward] = useState("");

  useEffect(() => {
    if (!open) return;
    setName(program?.name ?? "");
    setPlatform(program?.platform ?? "");
    setUrl(program?.url ?? "");
    setReward(program?.reward_info ?? "");
  }, [open, program]);

  const save = useMutation({
    meta: { silent: true },
    mutationFn: () => {
      const data = {
        name: name.trim(),
        platform: platform.trim() || null,
        url: url.trim() || null,
        reward_info: reward.trim() || null,
      };
      return program ? api.programs.update(program.id, data) : api.programs.create(data);
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ["programs"] });
      if (program) qc.invalidateQueries({ queryKey: ["program", program.id] });
      onOpenChange(false);
      onSaved?.(saved);
    },
  });

  const editing = !!program;
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) save.reset();
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) save.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>{editing ? "Edit program" : "New program"}</DialogTitle>
            <DialogDescription>
              {editing ? "Update the program details." : "Add a bug bounty program to track."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="program-name">Program name</Label>
            <Input
              id="program-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Corp"
              required
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="program-platform">Platform</Label>
            <Input
              id="program-platform"
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              placeholder="HackerOne, Bugcrowd, Intigriti…"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="program-url">URL</Label>
            <Input
              id="program-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://hackerone.com/acme"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="program-reward">Reward info</Label>
            <Input
              id="program-reward"
              value={reward}
              onChange={(e) => setReward(e.target.value)}
              placeholder="$100 – $5,000 per valid report"
            />
          </div>
          {save.error ? (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(save.error)}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending || !name.trim()}>
              {save.isPending ? "Saving…" : editing ? "Save changes" : "Add program"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
