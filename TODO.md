# Project Explorer App - TODO List

This file tracks potential improvements for the `code_to_gpt.py` application.

## Refactoring

-   [ ] Break down large methods (`__init__`, `create_widgets`, `save_preferences`, `load_preferences`, `update_selected_files`) into smaller, private methods.
    -   [ ] Refactor `__init__`
    -   [ ] Refactor `create_widgets`
    -   [ ] Refactor `load_preferences` / `save_preferences`
    -   [ ] Refactor `update_selected_files`

## Error Handling

-   [ ] Replace generic `except Exception:` blocks with specific exception types (`FileNotFoundError`, `PermissionError`, `json.JSONDecodeError`, `tk.TclError`, etc.).
-   [ ] Provide more informative user feedback (e.g., `messagebox.showerror`) for critical errors instead of just logging.
-   [ ] Add specific error handling for file reading in `on_generate_code`.

## Performance Optimization

-   [ ] Optimize `update_selected_files`: Avoid re-walking the entire directory on every change. Consider caching the file list and extensions.
-   [ ] Investigate potential UI blocking when reading many/large files in `on_generate_code`. Consider threading/async if needed.

## Modernize Python Usage

-   [x] Replace `os` module usage with `pathlib` for path manipulations.
-   [x] Use f-strings for string formatting.

## Code Structure and Readability

-   [x] Define constants for filenames, default values, and magic numbers/strings.
-   [x] Sort imports according to PEP 8 and remove unused imports.
-   [x] Identify and remove redundant code (e.g., `known_text_extensions` definition, duplicated theme/fullscreen init).
    -   [x] `known_text_extensions` definition removed
    -   [x] duplicated theme/fullscreen init
-   [ ] Ensure general adherence to PEP 8 style guidelines.

## UI Responsiveness

-   [ ] Double-check that all potentially long-running operations are offloaded to threads.
-   [ ] Ensure UI updates from threads are correctly handled via the queue.

## Logging

-   [ ] Review and improve logging messages for clarity and consistency.
-   [ ] Remove any remaining `print` statements used for debugging.

## Class Design

-   [ ] Review coupling between `SettingsWindow` and `ProjectExplorerApp`. Consider passing values or using callbacks instead of direct attribute access (`self.app.*`).

## Specific Functionality Review

-   [ ] Review `update_selected_files` logic for combining extension-based and manual selections. Ensure correctness and efficiency.
-   [ ] Review `add_selected_file` and `remove_selected_file` logic.
-   [ ] Review `on_generate_code` logic and separators.
-   [ ] Review search functionality (simple and advanced) for correctness and efficiency.
-   [ ] Review drag-and-drop handling.
-   [ ] Review context menu logic (enabling/disabling items).
