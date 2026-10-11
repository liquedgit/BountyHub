"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/auth/password-input";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RegistrationClosedError, register } from "@/features/auth/api";

export const MIN_PASSWORD_LENGTH = 8;

export function RegisterForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);

  const mutation = useMutation({
    mutationFn: register,
    onSuccess: () => {
      router.replace("/");
      router.refresh();
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    mutation.mutate({ email, password });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <PasswordInput
          id="password"
          
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="confirm-password">Confirm password</Label>
        <PasswordInput
          id="confirm-password"
          
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </div>
      {mismatch && (
        <p role="alert" className="text-sm text-destructive">
          Passwords do not match
        </p>
      )}
      {mutation.isError && (
        <p role="alert" className="text-sm text-destructive">
          {mutation.error.message}
          {mutation.error instanceof RegistrationClosedError && (
            <>
              {" "}
              <Link href="/login" className="underline">
                Sign in
              </Link>
            </>
          )}
        </p>
      )}
      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? "Creating account…" : "Create account"}
      </Button>
    </form>
  );
}
