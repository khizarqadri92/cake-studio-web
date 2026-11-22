import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

const base = "w-full rounded-xl border border-primary/20 bg-surface px-4 py-2.5 text-sm placeholder:text-ink/40 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20";
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className = "", ...p }, ref) => (
  <input ref={ref} className={`${base} ${className}`} {...p} />
));
Input.displayName = "Input";
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className = "", ...p }, ref) => (
  <textarea ref={ref} className={`${base} ${className}`} {...p} />
));
Textarea.displayName = "Textarea";
