# -*- coding: utf-8 -*-
"""
片段合并器 v1.0 — 视频无损合并工具
===================================
痛点：多个同格式视频片段需要合并为单个文件，传统方法需要重新编码，耗时长且损失画质。

解决方案：使用 ffmpeg concat demuxer（流拷贝模式）实现无损合并，不重新编码，
速度仅受磁盘 I/O 限制，画质零损失。

功能：
  - 选择多个同格式视频文件（支持拖拽排序）
  - 自动检测文件格式是否一致（不一致时警告）
  - 用 ffmpeg concat 流拷贝无损合并
  - 输出到源文件夹，含进度提示
  - 未安装 ffmpeg 时提示安装

依赖：仅使用 Python 标准库，外部依赖 ffmpeg（需自行安装）。
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

# ============================================================================
# 配色与常量
# ============================================================================
COLOR_BG = "#1e1e2e"
COLOR_CARD = "#2a2a3c"
COLOR_ACCENT = "#4ade80"          # 绿色强调
COLOR_ACCENT_HOVER = "#22c55e"
COLOR_TEXT = "#e0e0e0"
COLOR_TEXT_SECONDARY = "#a0a0b0"
COLOR_ENTRY_BG = "#3a3a4c"
COLOR_WARN = "#fbbf24"
COLOR_DANGER = "#f87171"

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".mts", ".m2ts"}


# ============================================================================
# 工具函数
# ============================================================================

def find_ffmpeg() -> str | None:
    """在 PATH 中查找 ffmpeg.exe，返回路径或 None"""
    result = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split("\n")[0].strip()
    # 尝试常见安装路径
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*\ffmpeg.exe"),
    ]
    for p in common_paths:
        if "*" in p:
            import glob
            matches = glob.glob(p)
            if matches:
                return matches[0]
        elif os.path.exists(p):
            return p
    return None


def get_file_format(file_path: str) -> str:
    """获取文件扩展名（小写，不含点）"""
    return Path(file_path).suffix.lower()


# ============================================================================
# 主程序
# ============================================================================

class ClipMergeApp:
    """片段合并器 v1.0"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("片段合并器 v1.0")
        self.root.geometry("500x350")
        self.root.resizable(False, False)
        self.root.configure(bg=COLOR_BG)

        self.video_files: list[str] = []   # 完整路径列表
        self.ffmpeg_path: str | None = None
        self.merge_process: subprocess.Popen | None = None

        self._setup_styles()
        self._check_ffmpeg()
        self._build_ui()

    # ------------------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=("微软雅黑", 9))
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        style.configure("Card.TLabelframe", background=COLOR_CARD, foreground=COLOR_ACCENT)
        style.configure("Card.TLabelframe.Label", background=COLOR_CARD, foreground=COLOR_ACCENT,
                        font=("微软雅黑", 10, "bold"))
        style.configure("Accent.TButton", background=COLOR_ACCENT, foreground="#111827",
                        borderwidth=0, font=("微软雅黑", 9, "bold"))
        style.map("Accent.TButton", background=[("active", COLOR_ACCENT_HOVER)])
        style.configure("Secondary.TButton", background="#444466", foreground=COLOR_TEXT, borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#555577")])

    # ------------------------------------------------------------------
    def _check_ffmpeg(self):
        """检测 ffmpeg 是否可用"""
        self.ffmpeg_path = find_ffmpeg()

    # ------------------------------------------------------------------
    def _build_ui(self):
        """构建界面"""
        pad = {"padx": 8, "pady": 2}

        # ---- 文件列表区域 ----
        frm_list = ttk.LabelFrame(self.root, text="视频片段列表（按合并顺序）", style="Card.TLabelframe")
        frm_list.pack(fill=tk.BOTH, expand=True, **pad, pady=(8, 2))

        list_frame = tk.Frame(frm_list, bg=COLOR_CARD)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        self.listbox = tk.Listbox(
            list_frame, height=8, bg=COLOR_ENTRY_BG, fg=COLOR_TEXT,
            font=("Consolas", 9), selectbackground=COLOR_ACCENT,
            selectforeground="#111827", relief=tk.FLAT,
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        # 按钮行
        btn_frame = tk.Frame(self.root, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, **pad, pady=(2, 2))

        ttk.Button(btn_frame, text="添加视频", command=self._on_add_files,
                   style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="上移", command=lambda: self._move_item(-1),
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="下移", command=lambda: self._move_item(1),
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="移除选中", command=self._on_remove_selected,
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="清空列表", command=self._on_clear_list,
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)

        # ---- 状态信息 ----
        info_frame = tk.Frame(self.root, bg=COLOR_BG)
        info_frame.pack(fill=tk.X, **pad)

        self.lbl_info = tk.Label(info_frame, text="请添加同格式视频文件", bg=COLOR_BG,
                                  fg=COLOR_TEXT_SECONDARY, font=("微软雅黑", 8), anchor=tk.W)
        self.lbl_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ffmpeg 状态指示
        ff_status = "ffmpeg: 已检测到" if self.ffmpeg_path else "ffmpeg: 未检测到"
        ff_color = COLOR_ACCENT if self.ffmpeg_path else COLOR_DANGER
        self.lbl_ffmpeg = tk.Label(info_frame, text=ff_status, bg=COLOR_BG,
                                    fg=ff_color, font=("微软雅黑", 8))
        self.lbl_ffmpeg.pack(side=tk.RIGHT)

        # ---- 进度条 ----
        self.progress = ttk.Progressbar(self.root, mode="indeterminate", length=480)
        self.progress.pack(fill=tk.X, **pad, pady=(2, 2))

        # ---- 合并按钮 ----
        self.btn_merge = ttk.Button(
            self.root, text="开始无损合并", command=self._on_merge,
            style="Accent.TButton",
        )
        self.btn_merge.pack(pady=(2, 8), ipadx=20, ipady=4)
        self.btn_merge.configure(state="disabled")

    # ------------------------------------------------------------------
    # 文件操作
    # ------------------------------------------------------------------

    def _on_add_files(self):
        """添加视频文件到列表"""
        files = filedialog.askopenfilenames(
            title="选择视频文件（同格式）",
            filetypes=[("视频文件", "*.mp4 *.mov *.avi *.mkv *.wmv *.flv *.webm *.m4v *.ts *.mts"),
                       ("所有文件", "*.*")],
        )
        if not files:
            return

        # 校验格式一致性
        new_exts = {get_file_format(f) for f in files}
        existing_exts = {get_file_format(f) for f in self.video_files} if self.video_files else set()

        if existing_exts and new_exts != existing_exts:
            messagebox.showwarning("格式不一致",
                f"已添加文件格式 ({', '.join(new_exts)}) 与列表中已有格式 ({', '.join(existing_exts)}) 不一致。\n"
                f"无损合并要求所有文件格式相同，请确认。")

        for f in files:
            if f not in self.video_files:
                self.video_files.append(f)
                self.listbox.insert(tk.END, f"  {os.path.basename(f)}")

        self._update_info()

    def _move_item(self, direction: int):
        """上移/下移选中项（direction: -1 上移, +1 下移）"""
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.video_files):
            return

        # 交换数据
        self.video_files[idx], self.video_files[new_idx] = self.video_files[new_idx], self.video_files[idx]
        # 刷新列表显示
        self._refresh_listbox()
        self.listbox.selection_set(new_idx)

    def _on_remove_selected(self):
        """移除选中项"""
        sel = self.listbox.curselection()
        if not sel:
            return
        for idx in reversed(sel):
            del self.video_files[idx]
        self._refresh_listbox()
        self._update_info()

    def _on_clear_list(self):
        """清空列表"""
        self.video_files.clear()
        self.listbox.delete(0, tk.END)
        self._update_info()

    def _refresh_listbox(self):
        """刷新 Listbox 内容"""
        self.listbox.delete(0, tk.END)
        for f in self.video_files:
            self.listbox.insert(tk.END, f"  {os.path.basename(f)}")

    def _update_info(self):
        """更新状态信息"""
        n = len(self.video_files)
        exts = {get_file_format(f) for f in self.video_files}

        if n == 0:
            self.lbl_info.config(text="请添加同格式视频文件", fg=COLOR_TEXT_SECONDARY)
            self.btn_merge.configure(state="disabled")
            return

        if len(exts) > 1:
            self.lbl_info.config(text=f"⚠ 格式不一致：{', '.join(exts)}（共 {n} 个文件）",
                                  fg=COLOR_DANGER)
            self.btn_merge.configure(state="disabled")
            return

        self.lbl_info.config(
            text=f"已添加 {n} 个 {list(exts)[0]} 文件，将无损合并",
            fg=COLOR_ACCENT,
        )
        self.btn_merge.configure(
            state="normal" if self.ffmpeg_path and n >= 2 else "disabled"
        )
        if n < 2 and n > 0:
            self.lbl_info.config(text="至少需要 2 个文件才能合并", fg=COLOR_WARN)

    # ------------------------------------------------------------------
    # 合并逻辑
    # ------------------------------------------------------------------

    def _on_merge(self):
        """执行合并"""
        if not self.ffmpeg_path:
            messagebox.showerror("缺少 ffmpeg",
                "未检测到 ffmpeg。请安装 ffmpeg 并添加到系统 PATH。\n"
                "下载地址：https://ffmpeg.org/download.html\n"
                "Windows 推荐：https://www.gyan.dev/ffmpeg/builds/ (ffmpeg-release-full.7z)")
            return

        if len(self.video_files) < 2:
            messagebox.showwarning("文件不足", "至少需要 2 个视频文件才能合并")
            return

        # 确定输出路径（源文件夹 + 时间戳命名）
        ext = get_file_format(self.video_files[0])
        src_dir = os.path.dirname(self.video_files[0])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(src_dir, f"merged_{timestamp}{ext}")

        # 确认覆盖
        if os.path.exists(output_path):
            if not messagebox.askyesno("文件已存在", f"{output_path}\n已存在，是否覆盖？"):
                return

        self.btn_merge.configure(state="disabled", text="合并中...")
        self.progress.start(10)

        thread = threading.Thread(target=self._merge_thread, args=(output_path,), daemon=True)
        thread.start()

    def _merge_thread(self, output_path: str):
        """后台线程执行 ffmpeg concat"""
        try:
            # 生成 ffmpeg concat 文件列表
            list_path = os.path.join(os.path.dirname(output_path),
                                     f"_ffconcat_temp_{datetime.now().strftime('%H%M%S%f')}.txt")
            with open(list_path, "w", encoding="utf-8") as f:
                for vf in self.video_files:
                    # ffmpeg concat 文件格式：file 'path'（需转义单引号）
                    escaped = vf.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            # 执行 ffmpeg concat demuxer（流拷贝，无损）
            cmd = [
                self.ffmpeg_path, "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_path,
                "-c", "copy",           # 流拷贝，不重新编码
                "-map", "0",
                output_path,
            ]

            # 静默运行，捕获错误
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

            # 清理临时文件
            try:
                os.remove(list_path)
            except OSError:
                pass

            if result.returncode == 0:
                out_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                self.root.after(0, self._on_merge_done, True, output_path, out_size, "")
            else:
                err_msg = result.stderr[-500:] if result.stderr else "未知错误"
                self.root.after(0, self._on_merge_done, False, output_path, 0, err_msg)

        except subprocess.TimeoutExpired:
            self.root.after(0, self._on_merge_done, False, output_path, 0, "合并超时（>1小时）")
        except Exception as e:
            self.root.after(0, self._on_merge_done, False, output_path, 0, str(e))

    def _on_merge_done(self, success: bool, path: str, size: int, error: str):
        """合并完成回调（主线程）"""
        self.progress.stop()
        self.btn_merge.configure(state="normal", text="开始无损合并")

        if success:
            size_str = f"{size / (1024*1024):.1f} MB" if size > 1024 * 1024 else f"{size / 1024:.1f} KB"
            messagebox.showinfo("合并完成",
                f"无损合并完成！\n\n"
                f"输出文件：{path}\n"
                f"文件大小：{size_str}\n"
                f"使用流拷贝模式，画质零损失。")
        else:
            messagebox.showerror("合并失败", f"合并过程中出错：\n{error}")


# ============================================================================
# 入口
# ============================================================================

def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    ClipMergeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
