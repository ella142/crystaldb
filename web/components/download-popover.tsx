"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { BundleAction, DownloadAction } from "@/lib/download-types";
import { downloadFile } from "@/lib/downloads";

interface DownloadPopoverProps {
  actions: DownloadAction[];
  bundle?: BundleAction;
  loading?: boolean;
  loadingLabel?: string;
  emptyLabel?: string;
  onOpen?: () => void;
}

export function DownloadPopover({
  actions,
  bundle,
  loading = false,
  loadingLabel = "Checking registered files…",
  emptyLabel = "No registered downloads",
  onOpen,
}: DownloadPopoverProps) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  function updatePosition() {
    const button = buttonRef.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const width = Math.min(390, window.innerWidth - 24);
    const left = Math.min(
      Math.max(12, rect.right - width),
      Math.max(12, window.innerWidth - width - 12),
    );
    const menuHeight = Math.min(420, window.innerHeight - 24);
    const belowTop = rect.bottom + 8;
    const top =
      belowTop + menuHeight <= window.innerHeight - 12
        ? belowTop
        : Math.max(12, rect.top - menuHeight - 8);
    setPosition({ top, left });
  }

  useEffect(() => {
    if (!open) return;
    updatePosition();
    const handleViewportChange = () => updatePosition();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!buttonRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [open]);

  function toggle() {
    const nextOpen = !open;
    setOpen(nextOpen);
    setError(null);
    if (nextOpen) onOpen?.();
  }

  async function handleDownload(action: DownloadAction) {
    setBusyId(action.id);
    setError(null);
    try {
      await downloadFile(action.url, action.filename);
      setOpen(false);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Download failed.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleBundle() {
    if (!bundle) return;
    setBusyId(bundle.id);
    setError(null);
    try {
      await bundle.onDownload();
      setOpen(false);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Bundle creation failed.");
    } finally {
      setBusyId(null);
    }
  }

  const groupedActions = actions.reduce<Record<string, DownloadAction[]>>((groups, action) => {
    (groups[action.group] ||= []).push(action);
    return groups;
  }, {});

  const menu =
    open && mounted
      ? createPortal(
          <div
            ref={menuRef}
            role="dialog"
            aria-label="Download data"
            className="fixed z-50 max-h-[min(70vh,560px)] w-[calc(100vw-24px)] overflow-y-auto rounded-lg border border-line bg-white p-4 shadow-panel"
            style={{ top: position.top, left: position.left, maxWidth: 390 }}
          >
            <div className="border-b border-line pb-3">
              <div className="eyebrow">Download data</div>
              <div className="mt-1 text-sm font-semibold text-ink">
                Available files and expected filenames
              </div>
            </div>
            {bundle ? (
              <div className="border-b border-line py-4">
                <button
                  type="button"
                  disabled={busyId !== null || loading}
                  onClick={handleBundle}
                  className="block w-full min-w-0 rounded-md border border-blue-200 bg-blue-50 px-3 py-3 text-left hover:bg-blue-100 disabled:cursor-wait disabled:opacity-60"
                >
                  <span className="block text-sm font-semibold text-blue-700">
                    {busyId === bundle.id ? "Preparing ZIP…" : bundle.label}
                  </span>
                  <span
                    className="mt-1 block min-w-0 break-words text-xs leading-5 text-slate-600"
                    title={bundle.filename}
                  >
                    {bundle.filename}
                  </span>
                </button>
              </div>
            ) : null}
            {loading ? (
              <div className="py-5 text-sm text-slate-500">{loadingLabel}</div>
            ) : Object.keys(groupedActions).length ? (
              <div className="space-y-5 pt-4">
                {Object.entries(groupedActions).map(([group, groupActions]) => (
                  <section key={group}>
                    <h3 className="data-label">{group}</h3>
                    <div className="mt-2 divide-y divide-line border-y border-line">
                      {groupActions.map((action) => (
                        <button
                          key={action.id}
                          type="button"
                          disabled={busyId !== null}
                          onClick={() => handleDownload(action)}
                          className="block w-full min-w-0 px-2 py-3 text-left hover:bg-blue-50 disabled:cursor-wait disabled:opacity-60"
                        >
                          <span className="block text-xs font-semibold text-ink">
                            {busyId === action.id ? "Preparing download…" : action.label}
                          </span>
                          <span
                            className="mt-1 block min-w-0 break-words text-xs leading-5 text-slate-500"
                            title={action.filename}
                          >
                            {action.filename}
                          </span>
                        </button>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              <div className="py-5 text-sm text-slate-500">{emptyLabel}</div>
            )}
            {error ? (
              <div role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-700">
                {error}
              </div>
            ) : null}
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={toggle}
        className="button-secondary whitespace-nowrap px-3 py-2 text-xs"
      >
        Download
      </button>
      {menu}
    </>
  );
}
