import { forwardRef, type ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";
const styles: Record<Variant, string> = {
  primary: "bg-primary text-white hover:opacity-90",
  secondary: "bg-secondary text-ink hover:opacity-90",
  ghost: "bg-transparent text-primary border border-primary/30 hover:bg-primary/5",
};
export const buttonClass = (v: Variant = "primary", extra = "") =>
  `inline-flex items-center justify-center gap-2 rounded-btn px-6 py-2.5 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 ${styles[v]} ${extra}`;

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }>(
  ({ variant = "primary", className = "", ...p }, ref) => <button ref={ref} className={buttonClass(variant, className)} {...p} />,
);
Button.displayName = "Button";
