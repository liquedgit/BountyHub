"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ErrorState } from "@/components/common/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errorMessage } from "@/lib/api";
import type { AIProvider, AISettingsUpdate } from "@/lib/types";

function SavedBadge({ set }: { set: boolean }) {
  return <Badge variant={set ? "success" : "secondary"}>{set ? "saved" : "not set"}</Badge>;
}

function Field({
  id,
  label,
  hint,
  badge,
  ...props
}: {
  id: string;
  label: string;
  hint?: React.ReactNode;
  badge?: React.ReactNode;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <Label htmlFor={id}>{label}</Label>
        {badge}
      </div>
      <Input id={id} {...props} />
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function AISettingsForm() {
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["settings", "ai"],
    queryFn: api.settings.getAI,
  });

  const [provider, setProvider] = useState<AIProvider>("claude");
  const [claudeModel, setClaudeModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [openaiModel, setOpenaiModel] = useState("");
  // Write-only credentials: never seeded from the server.
  const [claudeToken, setClaudeToken] = useState("");
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    if (!data) return;
    setProvider(data.provider === "openai_compatible" ? "openai_compatible" : "claude");
    setClaudeModel(data.claude_model ?? "");
    setBaseUrl(data.openai_base_url ?? "");
    setOpenaiModel(data.openai_model ?? "");
  }, [data]);

  const save = useMutation({
    mutationFn: () => {
      const body: AISettingsUpdate = {
        provider,
        claude_model: claudeModel,
        openai_base_url: baseUrl,
        openai_model: openaiModel,
      };
      // A blank secret is omitted: the backend treats a missing field as unchanged.
      if (claudeToken.trim()) body.claude_token = claudeToken.trim();
      if (apiKey.trim()) body.openai_api_key = apiKey.trim();
      return api.settings.updateAI(body);
    },
    onSuccess: (saved) => {
      setClaudeToken("");
      setApiKey("");
      qc.setQueryData(["settings", "ai"], saved);
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("AI settings saved");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (isLoading) {
    return (
      <Card aria-busy="true" aria-label="Loading AI settings">
        <CardHeader>
          <Skeleton className="h-6 w-40" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }
  if (error || !data) {
    return (
      <ErrorState error={error} title="Could not load AI settings" onRetry={() => refetch()} />
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI provider</CardTitle>
        <CardDescription>
          Used to score and label recon results. Credentials are write-only: they are never shown
          again, and leaving a field blank keeps the stored value.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="ai-provider">Provider</Label>
            <Select
              id="ai-provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value as AIProvider)}
            >
              <option value="claude">Claude Code token</option>
              <option value="openai_compatible">OpenAI-compatible</option>
            </Select>
          </div>

          {provider === "claude" ? (
            <>
              <Field
                id="claude-token"
                label="Claude token"
                type="password"
                autoComplete="new-password"
                value={claudeToken}
                onChange={(e) => setClaudeToken(e.target.value)}
                placeholder={data.claude_token_set ? "Leave blank to keep the saved token" : ""}
                badge={<SavedBadge set={data.claude_token_set} />}
                hint={
                  <>
                    Run <code className="rounded bg-muted px-1">claude setup-token</code> in a
                    terminal and paste the token it prints.
                  </>
                }
              />
              <Field
                id="claude-model"
                label="Claude model"
                value={claudeModel}
                onChange={(e) => setClaudeModel(e.target.value)}
                placeholder="Optional, e.g. claude-sonnet-4-5"
              />
            </>
          ) : (
            <>
              <Field
                id="openai-base-url"
                label="Base URL"
                type="url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.openai.com/v1"
              />
              <Field
                id="openai-api-key"
                label="API key"
                type="password"
                autoComplete="new-password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={data.openai_api_key_set ? "Leave blank to keep the saved key" : ""}
                badge={<SavedBadge set={data.openai_api_key_set} />}
              />
              <Field
                id="openai-model"
                label="Model"
                value={openaiModel}
                onChange={(e) => setOpenaiModel(e.target.value)}
                placeholder="e.g. gpt-4o-mini"
              />
            </>
          )}

          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
