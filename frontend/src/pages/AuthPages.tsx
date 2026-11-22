import { useEffect, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { ApiError, post } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSeo } from "@/lib/theme";

type Mode = "login" | "register" | "forgot" | "reset" | "verify";
const titles: Record<Mode, string> = { login: "Log in", register: "Create your account", forgot: "Forgot password", reset: "Choose a new password", verify: "Confirm your email" };

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block text-sm"><span className="mb-1 block font-medium">{label}</span>{children}</label>;
}

function Verify() {
  const [params] = useSearchParams();
  const [state, setState] = useState<"working" | "ok" | "bad">("working");
  const { reload } = useAuth();
  useEffect(() => {
    const token = params.get("token");
    if (!token) { setState("bad"); return; }
    post("/auth/customer/verify-email", { token }).then(() => { setState("ok"); void reload(); }).catch(() => setState("bad"));
  }, [params, reload]);
  if (state === "working") return <p>Confirming…</p>;
  return state === "ok"
    ? <p role="status">Your email is confirmed. <Link className="text-primary underline" to="/account">Go to your account</Link></p>
    : <p role="alert" className="text-red-700">This link is invalid or has expired. Log in and request a new one from your account page.</p>;
}

export default function AuthPages({ mode }: { mode: Mode }) {
  useSeo(titles[mode]);
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [f, setF] = useState({ email: "", password: "", full_name: "", phone: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const set = (k: keyof typeof f) => (e: ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      if (mode === "login") { await login(f.email, f.password); nav("/account", { replace: true }); return; }
      if (mode === "register") {
        await post("/auth/customer/register", { email: f.email, password: f.password, full_name: f.full_name, phone: f.phone || null });
        setDone("Almost there! If this email can be registered, we've sent a confirmation link to it. You can log in now with your new password.");
      }
      if (mode === "forgot") { await post("/auth/customer/password/forgot", { email: f.email }); setDone("If an account exists for that email, a reset link is on its way. It's valid for one hour."); }
      if (mode === "reset") { await post("/auth/customer/password/reset", { token: params.get("token") ?? "", password: f.password }); setDone("Password updated. Please log in with your new password."); }
    } catch (err) {
      setError(err instanceof ApiError ? (err.status === 429 ? "Too many attempts. Please wait a minute and try again." : err.message) : "Something went wrong");
    } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12 md:py-16">
      <div className="rounded-3xl bg-surface p-6 shadow-card md:p-8">
      <h1 className="text-center font-heading text-3xl">{titles[mode]}</h1>
      <div className="mt-6">
        {mode === "verify" ? <Verify /> : done ? (
          <p role="status" className="rounded-xl bg-secondary/40 p-4 text-sm">{done} {(mode === "reset" || mode === "register") && <Link className="text-primary underline" to="/account/login">Log in</Link>}</p>
        ) : (
          <form onSubmit={submit} className="space-y-4" noValidate>
            {mode === "register" && <Field label="Full name"><Input required autoComplete="name" value={f.full_name} onChange={set("full_name")} /></Field>}
            {mode !== "reset" && <Field label="Email"><Input required type="email" autoComplete="email" value={f.email} onChange={set("email")} /></Field>}
            {mode === "register" && <Field label="Phone (optional)"><Input type="tel" autoComplete="tel" value={f.phone} onChange={set("phone")} /></Field>}
            {mode !== "forgot" && (
              <Field label={mode === "reset" ? "New password" : "Password"}>
                <Input required type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={f.password} onChange={set("password")} />
                {(mode === "register" || mode === "reset") && <span className="mt-1 block text-xs text-ink/60">At least 10 characters. Avoid common passwords.</span>}
              </Field>
            )}
            {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full">{busy ? "Please wait…" : titles[mode]}</Button>
            <p className="text-center text-sm text-ink/70">
              {mode === "login" && <><Link className="text-primary underline" to="/account/forgot">Forgot password?</Link> · <Link className="text-primary underline" to="/account/register">Create account</Link></>}
              {mode === "register" && <>Already have an account? <Link className="text-primary underline" to="/account/login">Log in</Link></>}
              {(mode === "forgot" || mode === "reset") && <Link className="text-primary underline" to="/account/login">Back to log in</Link>}
            </p>
          </form>
        )}
      </div>
      </div>
    </div>
  );
}
