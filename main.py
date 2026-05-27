"""main.py — ORO QC Checker v2  (2-step UX: report picker → folder picker)"""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

import config
import doc_classifier
import pdf_parser
import ai_extractor
import rule_checker
import online_checker
import report_generator

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


# ─── helpers ────────────────────────────────────────────────────────────────
def _short(path: str, max_len: int = 70) -> str:
    name = os.path.basename(path) if path else "—"
    return ("…" + name[-(max_len - 1):]) if len(name) > max_len else name


# ─── Main Application ────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CHFT  ORO QC Checker  v2")
        self.geometry("800x640")
        self.resizable(False, False)

        self.report_path: str = ""
        self.folder_path: str = ""
        self.scan_result: dict = {}

        # ── Title bar ────────────────────────────────────────────────────────
        bar = ctk.CTkFrame(self, fg_color="#1a3a5c", corner_radius=0, height=54)
        bar.pack(fill="x")
        ctk.CTkLabel(bar, text="CHFT  |  ORO Valuation QC Checker",
                     font=ctk.CTkFont("Helvetica", 16, "bold"),
                     text_color="white").pack(side="left", padx=18, pady=14)
        ctk.CTkLabel(bar, text="v2.0", font=ctk.CTkFont("Helvetica", 10),
                     text_color="#aabbcc").pack(side="right", padx=18)

        # ── Body ─────────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="#f5f7fa", corner_radius=0)
        body.pack(fill="both", expand=True, padx=0, pady=0)

        # Step 1
        self._make_step_row(body, "Step 1", "Select the Valuation Report PDF to be checked:",
                            "Browse Report…", self._pick_report)
        self.lbl_report = ctk.CTkLabel(body, text="No report selected.",
                                       text_color="#555", font=ctk.CTkFont(size=11))
        self.lbl_report.pack(anchor="w", padx=28, pady=(0, 6))

        # Step 2
        self._make_step_row(body, "Step 2",
                            "Select the folder containing supporting / cross-check documents:",
                            "Browse Folder…", self._pick_folder)
        self.lbl_folder = ctk.CTkLabel(body, text="No folder selected.",
                                       text_color="#555", font=ctk.CTkFont(size=11))
        self.lbl_folder.pack(anchor="w", padx=28, pady=(0, 6))

        # Document list box
        ctk.CTkLabel(body, text="Documents detected in folder:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#1a3a5c").pack(anchor="w", padx=28, pady=(10, 2))
        self.doc_box = ctk.CTkTextbox(body, height=160, font=ctk.CTkFont("Courier", 10),
                                      fg_color="#ffffff", text_color="#333")
        self.doc_box.pack(fill="x", padx=28, pady=(0, 8))
        self.doc_box.configure(state="disabled")

        # API key row
        api_row = ctk.CTkFrame(body, fg_color="transparent")
        api_row.pack(fill="x", padx=28, pady=(0, 6))
        ctk.CTkLabel(api_row, text="OpenAI API Key (optional):",
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self.api_entry = ctk.CTkEntry(api_row, width=320, show="•",
                                      placeholder_text="sk-…  (leave blank to skip AI checks)")
        self.api_entry.pack(side="left", padx=8)
        saved_key = config.get_api_key()
        if saved_key:
            self.api_entry.insert(0, saved_key)

        # Progress bar + label
        self.progress = ctk.CTkProgressBar(body, width=740, height=14)
        self.progress.pack(padx=28, pady=(4, 2))
        self.progress.set(0)
        self.lbl_progress = ctk.CTkLabel(body, text="Ready.",
                                         font=ctk.CTkFont(size=11), text_color="#555")
        self.lbl_progress.pack(anchor="w", padx=28)

        # Run button
        self.btn_run = ctk.CTkButton(body, text="▶  Run QC Check",
                                     font=ctk.CTkFont(size=13, weight="bold"),
                                     fg_color="#1a3a5c", hover_color="#2563eb",
                                     height=40, command=self._run)
        self.btn_run.pack(pady=14)

        # Footer
        ctk.CTkLabel(self, text="CHFT Advisory and Appraisal Ltd.  |  For internal use only",
                     font=ctk.CTkFont(size=9), text_color="#999").pack(pady=(0, 6))

    # ── Row helper ────────────────────────────────────────────────────────────
    def _make_step_row(self, parent, step_tag, label_text, btn_text, cmd):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(12, 2))
        ctk.CTkLabel(row, text=step_tag, width=54,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     fg_color="#1a3a5c", text_color="white",
                     corner_radius=6).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row, text=label_text,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkButton(row, text=btn_text, width=150, height=30,
                      command=cmd).pack(side="right", padx=(0, 8))

    # ── Pickers ───────────────────────────────────────────────────────────────
    def _pick_report(self):
        path = filedialog.askopenfilename(
            title="Select the Valuation Report PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        self.report_path = path
        self.lbl_report.configure(text=f"  ✔  {_short(path)}", text_color="#16a34a")
        if self.folder_path:
            self._refresh_scan()

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Supporting Documents")
        if not folder:
            return
        self.folder_path = folder
        self.lbl_folder.configure(text=f"  ✔  {folder}", text_color="#16a34a")
        if self.report_path:
            self._refresh_scan()

    def _refresh_scan(self):
        """Re-scan folder and update the document list box."""
        self._set_progress(0.05, "Scanning folder…")
        self.scan_result = doc_classifier.scan_folder(self.folder_path, self.report_path)
        sup = self.scan_result.get("supporting", {})
        excl = self.scan_result.get("excluded_reports", [])

        lines = []
        type_labels = {
            "land_register":      "Land Register       ",
            "rvd":                "RVD Printout        ",
            "assignment":         "Assignment          ",
            "instruction_letter": "Instruction Letter  ",
        }
        for k, lbl in type_labels.items():
            v = sup.get(k)
            lines.append(f"  {'✔' if v else '—'}  {lbl}  {_short(v) if v else '(not found)'}")
        for p in sup.get("unknown", []):
            lines.append(f"  ·  Other               {_short(p)}")
        for p in excl:
            lines.append(f"  ✖  [Excluded-report]   {_short(p)}")

        self.doc_box.configure(state="normal")
        self.doc_box.delete("1.0", "end")
        self.doc_box.insert("end", "\n".join(lines) if lines else "  (no PDFs found in folder)")
        self.doc_box.configure(state="disabled")
        self._set_progress(0, "Ready.")

    # ── Progress helpers ──────────────────────────────────────────────────────
    def _set_progress(self, value: float, msg: str):
        self.progress.set(value)
        self.lbl_progress.configure(text=msg)
        self.update_idletasks()

    # ── Run ───────────────────────────────────────────────────────────────────
    def _run(self):
        if not self.report_path:
            messagebox.showwarning("Missing Input", "Please select the valuation report PDF first.")
            return
        if not self.folder_path:
            messagebox.showwarning("Missing Input", "Please select the supporting documents folder.")
            return

        # Save API key if entered
        entered_key = self.api_entry.get().strip()
        if entered_key and entered_key.startswith("sk-"):
            config.save_api_key(entered_key)

        self.btn_run.configure(state="disabled", text="Running…")
        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    def _run_pipeline(self):
        try:
            self._set_progress(0.05, "Reading valuation report…")
            report_text = pdf_parser.extract_full_text(self.report_path)

            self._set_progress(0.15, "Extracting data from report…")
            extracted = ai_extractor.extract_all(
                report_text=report_text,
                scan_result=self.scan_result,
            )

            self._set_progress(0.40, "Running rule-based checks…")
            findings = rule_checker.run_all_checks(extracted)

            self._set_progress(0.65, "Verifying online facts…")
            estate_name = (extracted.get("valuation") or {}).get("estate_name", "")
            val_data    = extracted.get("valuation") or {}
            o_findings  = online_checker.run_online_checks(estate_name, val_data)

            self._set_progress(0.80, "Generating PDF report…")
            val = extracted.get("valuation") or {}
            out_name = f"QC_Report_{os.path.splitext(os.path.basename(self.report_path))[0]}.pdf"
            out_path = os.path.join(self.folder_path, out_name)

            report_generator.generate_pdf_report(
                findings=findings,
                online_findings=o_findings,
                property_address=val.get("property_address", ""),
                oro_ref=val.get("oro_ref", ""),
                chft_ref=val.get("chft_ref", ""),
                output_path=out_path,
                extracted_data=extracted,
                folder_scan=self.scan_result,
            )

            self._set_progress(1.0, f"Done! Report saved to: {_short(out_path, 80)}")
            self.after(0, lambda: self._on_done(out_path))

        except Exception as e:
            self.after(0, lambda: self._on_error(str(e)))

    def _on_done(self, out_path: str):
        self.btn_run.configure(state="normal", text="▶  Run QC Check")
        messagebox.showinfo(
            "QC Complete",
            f"QC Report saved:\n\n{out_path}\n\nPlease open the PDF to review findings.",
        )

    def _on_error(self, msg: str):
        self.btn_run.configure(state="normal", text="▶  Run QC Check")
        self._set_progress(0, "Error — see message.")
        messagebox.showerror("Error", f"QC check failed:\n\n{msg}")


# ─── Entry point ────────────────────────────────────────────────────────────
def main():
    # On Windows, hide the console window that PyInstaller might create
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
