# Camera Display Issues - Troubleshooting Log

## Problem
The camera stream is successfully captured and frames are being read (verified by console output showing frame shapes and counts), but the image does not display in the Tkinter GUI. The error "image 'pyimageXX' doesn't exist" occurs when trying to display PhotoImage objects.

## Root Cause
This is a known Tkinter PhotoImage garbage collection issue. PhotoImage objects are being created successfully (verified by object IDs in console output), but they are being garbage collected by Python before Tkinter can use them, even when stored in multiple reference locations.

## Attempted Solutions

### 1. Reference Management Approaches
**Attempted:**
- Storing PhotoImage in instance variable (`self.camera_photo`)
- Storing PhotoImage on label widget (`self.camera_label.image = photo`)
- Storing PhotoImage in a list (`self._camera_photo_list`)
- Storing PhotoImage on root widget (`self.root._camera_photos`)
- Storing PhotoImage in multiple places simultaneously

**Result:** PhotoImage still gets garbage collected despite multiple references.

### 2. Widget Type Changes
**Attempted:**
- Initially used `tk.Label` with `config(image=photo)`
- Switched to `tk.Canvas` with `create_image()` method
- Switched back to `tk.Label` with persistent PhotoImage

**Result:** Same garbage collection issue with both widget types.

### 3. Timing and Scheduling Approaches
**Attempted:**
- Using `root.after(50, callback)` for periodic updates
- Using `root.update_idletasks()` to force Tkinter processing
- Creating PhotoImage and using it immediately in same function call
- Storing PhotoImage before calling `config()`

**Result:** PhotoImage still gets garbage collected.

### 4. Garbage Collection Workarounds
**Attempted:**
- Temporarily disabling Python's garbage collector with `gc.disable()` during PhotoImage creation and use
- Keeping PhotoImage references in multiple data structures
- Using `finally` blocks to ensure references are maintained

**Result:** Still experiencing garbage collection issues.

### 5. Code Structure Changes
**Attempted:**
- Creating PhotoImage in main thread (already the case via `root.after()`)
- Using PhotoImage from stored reference vs. local variable
- Verifying PhotoImage exists before using it
- Adding extensive debug output to track PhotoImage lifecycle

**Result:** PhotoImage objects are created (verified by IDs) but Tkinter reports they don't exist when used.

## Current State

### What Works:
- Camera stream connection (verified: frames are being captured)
- Frame capture loop (verified: console shows "Camera: Captured X frames")
- Frame processing (verified: frames are converted to PIL images and PhotoImages are created)
- PhotoImage creation (verified: PhotoImage objects are created with valid IDs)

### What Doesn't Work:
- PhotoImage display in Tkinter (error: "image 'pyimageXX' doesn't exist")
- Image appears in browser when accessing stream URL directly (confirms stream is working)

## Technical Details

### Frame Capture:
- Frames are captured at 640x480 resolution
- Frames are successfully converted from BGR to RGB
- PIL Images are created successfully
- PhotoImage objects are created with valid dimensions

### Error Pattern:
```
Display update #1: Created PhotoImage, size: 640x480, id: [ID]
Display update #1: Updating label, photo_id: [ID], list_size: 1
Display TclError at update #1: image "pyimage12" doesn't exist
```

The PhotoImage is created (ID is shown), stored in list, but Tkinter can't find it when `config(image=photo)` is called.

## Potential Future Solutions

### Option 1: Use Different GUI Framework
- PyQt/PySide (better image handling)
- wxPython (more robust image display)
- Kivy (modern GUI framework)

### Option 2: Embed Web Browser Widget
- Use `tkinterhtml` or similar to embed browser
- Display stream directly in browser widget
- Stream already works in browser, so this would leverage that

### Option 3: Save Frames to Temporary Files
- Save each frame to a temporary file
- Load file using `PhotoImage(file=path)` instead of `PhotoImage(image=pil_image)`
- File-based PhotoImage might avoid GC issues

### Option 4: Use OpenCV's Tkinter Integration
- Use `cv2.imshow()` in a separate window
- Or use OpenCV's GUI components directly

### Option 5: Lower-Level Tkinter Approach
- Use `tkinter.PhotoImage` with file-based loading
- Create PhotoImage from file path instead of PIL Image object
- May avoid the in-memory PhotoImage GC issue

### Option 6: Threading Investigation
- Ensure PhotoImage is created and used in main thread only
- Verify no threading issues with Tkinter's image registry
- Check if Tkinter version has known PhotoImage GC bugs

## Files Modified
- `gui/motor_control_gui/main.py`:
  - Camera display section (lines ~846-870)
  - `_update_camera_display()` method (lines ~1948-2113)
  - PhotoImage creation and storage logic

## Key Code Locations
- Camera label creation: `_build_camera_placeholder()` method
- Display update loop: `_update_camera_display()` method
- PhotoImage creation: Inside `_update_camera_display()` when processing frames

## Notes
- The camera stream works perfectly when accessed via browser (http://localhost:8080/stream)
- This confirms the issue is purely with Tkinter PhotoImage display, not the stream itself
- The standalone camera app displays frames correctly using OpenCV's `cv2.imshow()`
- This suggests the issue is specific to Tkinter's PhotoImage handling in this context

## References
- Tkinter PhotoImage garbage collection is a known issue
- PhotoImage objects must be kept alive by maintaining references
- Standard pattern: `widget.image = photo` before using `config(image=photo)`
- However, even following best practices, GC issues can still occur in some scenarios

