import os
import json
import shutil
from pathlib import Path
from tkinter import filedialog, simpledialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

CATEGORIES_FILE = "categories.json"

DEFAULT_CATEGORIES = {
    "Documents": ["pdf", "doc", "docx", "txt", "xls", "xlsx", "ppt", "pptx", "csv"],
    "Images": ["jpg", "jpeg", "png", "gif", "bmp", "svg"],
    "Videos": ["mp4", "mkv", "avi", "mov", "flv"],
    "Music": ["mp3", "wav", "aac", "flac", "m4a"],
    "Executables": ["exe", "msi", "bat", "sh", "jar"],
    "Archives": ["zip", "rar", "7z", "tar", "gz"]
}


class FileOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart File Organizer")
        self.root.geometry("900x550")

        self.style = ttk.Style("superhero")  # Themes: cyborg, flatly, cosmo, superhero, darkly

        self.custom_categories = self.load_categories()

        # --- Title ---
        title = ttk.Label(
            root,
            text="📂 Drag & Drop File Organizer",
            font=("Segoe UI", 18, "bold"),
            anchor="center"
        )
        title.pack(pady=10)

        # --- Path Selector ---
        top_frame = ttk.Frame(root, padding=10)
        top_frame.pack(fill=X)
        self.path_var = ttk.StringVar()
        self.path_entry = ttk.Entry(top_frame, textvariable=self.path_var, width=70)
        self.path_entry.pack(side=LEFT, padx=(0, 5))
        ttk.Button(top_frame, text="Browse Folder", bootstyle=PRIMARY, command=self.choose_folder).pack(side=LEFT)

        # Enable drag & drop on path entry
        self.path_entry.drop_target_register(DND_FILES)
        self.path_entry.dnd_bind("<<Drop>>", self.drop_folder)

        # --- Main Layout ---
        main_pane = ttk.Panedwindow(root, orient=HORIZONTAL)
        main_pane.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # --- Left: Custom Categories ---
        left_frame = ttk.Labelframe(main_pane, text="Custom Categories", padding=10)
        main_pane.add(left_frame, weight=1)

        self.category_list = ttk.Treeview(left_frame, columns=("Folder"), show="headings", height=12)
        self.category_list.heading("Folder", text="Folder Name")
        self.category_list.column("Folder", width=150)
        self.category_list.pack(fill=BOTH, expand=True, pady=(0, 10))

        for ext, folder in self.custom_categories.items():
            self.category_list.insert("", END, values=(f".{ext} → {folder}"))

        cat_btns = ttk.Frame(left_frame)
        cat_btns.pack(fill=X)
        ttk.Button(cat_btns, text="➕ Add", bootstyle=SUCCESS, command=self.add_category).pack(side=LEFT, expand=True, padx=3)
        ttk.Button(cat_btns, text="✏️ Edit", bootstyle=INFO, command=self.edit_category).pack(side=LEFT, expand=True, padx=3)
        ttk.Button(cat_btns, text="❌ Remove", bootstyle=DANGER, command=self.remove_category).pack(side=LEFT, expand=True, padx=3)

        # --- Right: Logs ---
        right_frame = ttk.Labelframe(main_pane, text="Logs", padding=10)
        main_pane.add(right_frame, weight=2)
        self.log_text = ttk.Text(right_frame, wrap="word", height=20)
        self.log_text.pack(fill=BOTH, expand=True)

        # --- Bottom: Organize Button ---
        bottom_frame = ttk.Frame(root, padding=10)
        bottom_frame.pack(fill=X)
        ttk.Button(
            bottom_frame,
            text="🧹 ORGANIZE FILES",
            bootstyle=(SUCCESS, OUTLINE),
            command=self.sort_files,
            width=30
        ).pack(pady=5)

        # Drag & drop anywhere on window (bonus)
        root.drop_target_register(DND_FILES)
        root.dnd_bind("<<Drop>>", self.drop_folder)

    # === Drag-and-drop handling ===
    def drop_folder(self, event):
        path = event.data.strip("{}")  # Windows adds braces around dropped paths
        if os.path.isdir(path):
            self.path_var.set(path)
            self.log(f"📁 Folder selected via drag-and-drop: {path}")
        else:
            self.log(f"⚠️ Not a valid folder: {path}")

    # === Category Management ===
    def add_category(self):
        ext = simpledialog.askstring("Add Category", "Enter file extension (without dot):")
        if not ext:
            return
        folder = simpledialog.askstring("Assign Folder", f"Enter folder name for .{ext} files:")
        if not folder:
            return
        self.custom_categories[ext.lower()] = folder
        self.save_categories()
        self.refresh_category_list()

    def edit_category(self):
        selected = self.category_list.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a category to edit.")
            return
        ext_folder = self.category_list.item(selected[0], "values")[0]
        ext = ext_folder.split(" → ")[0].replace(".", "")
        new_folder = simpledialog.askstring("Edit Category", f"New folder name for .{ext} files:")
        if new_folder:
            self.custom_categories[ext] = new_folder
            self.save_categories()
            self.refresh_category_list()

    def remove_category(self):
        selected = self.category_list.selection()
        if not selected:
            messagebox.showinfo("Info", "Select a category to remove.")
            return
        ext_folder = self.category_list.item(selected[0], "values")[0]
        ext = ext_folder.split(" → ")[0].replace(".", "")
        del self.custom_categories[ext]
        self.save_categories()
        self.refresh_category_list()

    def refresh_category_list(self):
        for item in self.category_list.get_children():
            self.category_list.delete(item)
        for ext, folder in self.custom_categories.items():
            self.category_list.insert("", END, values=(f".{ext} → {folder}"))

    # === Folder & Sorting Logic ===
    def choose_folder(self):
        folder = filedialog.askdirectory(title="Select Target Folder")
        if folder:
            self.path_var.set(folder)
            self.log(f"📁 Folder selected: {folder}")

    def get_extension(self, filename):
        return Path(filename).suffix[1:].lower() if '.' in filename else ""

    def move_file(self, file, target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
            shutil.move(str(file), str(Path(target_dir) / file.name))
            self.log(f"✅ Moved {file.name} → {target_dir}")
        except Exception as e:
            self.log(f"⚠️ Error moving {file.name}: {e}")

    def sort_files(self):
        path = self.path_var.get().strip()
        if not path or not os.path.isdir(path):
            messagebox.showerror("Error", "Please select a valid folder!")
            return

        files = [f for f in Path(path).iterdir() if f.is_file()]
        if not files:
            self.log("No files found in the selected directory.")
            return

        for file in files:
            ext = self.get_extension(file.name)
            if ext in self.custom_categories:
                self.move_file(file, Path(path) / self.custom_categories[ext])
                continue
            for folder, exts in DEFAULT_CATEGORIES.items():
                if ext in exts:
                    self.move_file(file, Path(path) / folder)
                    break

        self.log("🎉 All files organized successfully!")

    # === Helpers ===
    def log(self, message):
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)

    def load_categories(self):
        if os.path.exists(CATEGORIES_FILE):
            try:
                with open(CATEGORIES_FILE, "r") as f:
                    data = json.load(f)
                return {item["extension"]: item["folder"] for item in data}
            except Exception as e:
                self.log(f"⚠️ Error loading categories: {e}")
        return {}

    def save_categories(self):
        data = [{"extension": k, "folder": v} for k, v in self.custom_categories.items()]
        try:
            with open(CATEGORIES_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log(f"⚠️ Error saving categories: {e}")


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = FileOrganizerApp(root)
    root.mainloop()
