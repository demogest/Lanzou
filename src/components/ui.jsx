import { forwardRef, useEffect, useRef } from "react";
import { clampProgress } from "../lib/downloadState.js";

function classNames(...names) {
  return names.filter(Boolean).join(" ");
}

export function Shell({ children }) {
  return <div className="shell">{children}</div>;
}

export function Workspace({ children }) {
  return <main className="workspace">{children}</main>;
}

export function Panel({ children, className }) {
  return <section className={classNames("panel", className)}>{children}</section>;
}

export function Button({ children, className, type = "button", variant = "secondary", ...props }) {
  return (
    <button className={classNames(variant !== "plain" && variant, className)} type={type} {...props}>
      {children}
    </button>
  );
}

export function IconButton({ children = "×", ...props }) {
  return (
    <Button className="icon-button" type="submit" variant="plain" {...props}>
      {children}
    </Button>
  );
}

export const TextInput = forwardRef(function TextInput({ autoComplete = "off", ...props }, ref) {
  return <input autoComplete={autoComplete} ref={ref} {...props} />;
});

export function Field({ children, id, label }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
    </div>
  );
}

export function InlineField({ children }) {
  return <div className="inline-field">{children}</div>;
}

export function ButtonGroup({ children, className }) {
  return <div className={className}>{children}</div>;
}

export function SectionHeading({ action, compact = false, metric, subtitle, title }) {
  return (
    <div className={classNames("section-heading", compact && "compact")}>
      <div>
        <h2>{title}</h2>
        {subtitle ? <p id="statusText">{subtitle}</p> : null}
      </div>
      {metric ? <strong id="totalPercent">{metric}</strong> : action}
    </div>
  );
}

export function ProgressBar({ id, label, value }) {
  const progress = clampProgress(value);

  return (
    <div className="progress-track" aria-label={label}>
      <div id={id} className="progress-fill" style={{ width: `${progress}%` }} />
    </div>
  );
}

export function MiniProgress({ value }) {
  return (
    <div className="mini-progress">
      <span style={{ width: `${clampProgress(value)}%` }} />
    </div>
  );
}

export function Modal({ children, className = "dialog", open, onClose }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open && !dialog.open) {
      dialog.showModal();
    }
    if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog className={className} ref={dialogRef} onClose={onClose}>
      {children}
    </dialog>
  );
}

export function ModalForm({ bodyClassName, children, className = "dialog", footer, open, onClose, title }) {
  return (
    <Modal className={className} open={open} onClose={onClose}>
      <form method="dialog">
        <header>
          <h2>{title}</h2>
          <IconButton aria-label="关闭" value="cancel" />
        </header>
        <div className={bodyClassName}>{children}</div>
        {footer ? <footer>{footer}</footer> : null}
      </form>
    </Modal>
  );
}

export function EmptyState({ children }) {
  return <div className="empty-state">{children}</div>;
}
