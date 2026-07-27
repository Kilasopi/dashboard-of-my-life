import { useState } from "react";
import { Dialog, VisuallyHidden } from "radix-ui";
import { NavLink } from "react-router-dom";
import { Activity, Code2, Home, Menu, Timer as TimerIcon, X } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: Home, end: true },
  { to: "/programming", label: "Programming Mode", icon: Code2, end: false },
  { to: "/timer", label: "Focus Timer", icon: TimerIcon, end: false },
  { to: "/system-health", label: "System Health", icon: Activity, end: false },
];

export function NavMenu() {
  const [open, setOpen] = useState(false);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="rounded-lg border bg-secondary p-2 text-foreground transition-colors hover:bg-muted compact:p-1"
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5 compact:h-3.5 compact:w-3.5" />
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 data-[state=open]:animate-in data-[state=open]:fade-in data-[state=closed]:animate-out data-[state=closed]:fade-out" />
        <Dialog.Content
          className="fixed inset-y-0 left-0 z-50 flex h-full w-64 flex-col gap-1 border-r bg-card p-3 text-card-foreground shadow-lg outline-none data-[state=open]:animate-in data-[state=open]:slide-in-from-left data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left"
        >
          <VisuallyHidden.Root asChild>
            <Dialog.Title>Navigation</Dialog.Title>
          </VisuallyHidden.Root>

          <div className="flex items-center justify-between px-1 pb-2">
            <span className="text-sm font-semibold">Menu</span>
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Close menu"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
