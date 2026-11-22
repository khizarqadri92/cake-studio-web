import { Link } from "react-router-dom";
import { buttonClass } from "./ui/button";

export const Spinner = () => (
  <div role="status" aria-label="Loading" className="flex justify-center py-16">
    <div className="h-8 w-8 animate-spin rounded-full border-4 border-secondary border-t-primary" />
  </div>
);
export const Empty = ({ title, hint }: { title: string; hint?: string }) => (
  <div className="rounded-2xl bg-surface p-10 text-center shadow-card">
    <p className="font-heading text-xl">{title}</p>
    {hint && <p className="mt-2 text-sm text-ink/60">{hint}</p>}
  </div>
);
export const ErrorBox = ({ message }: { message?: string }) => (
  <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-800">
    {message || "Something went wrong. Please try again."}
  </div>
);
export const NotFound = () => (
  <div className="mx-auto max-w-xl px-4 py-24 text-center">
    <h1 className="text-4xl">Page not found</h1>
    <p className="mt-3 text-ink/70">We couldn't find what you were looking for.</p>
    <Link to="/" className={buttonClass("primary", "mt-6")}>Back to home</Link>
  </div>
);
