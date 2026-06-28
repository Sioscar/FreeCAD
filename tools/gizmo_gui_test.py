"""Headless GUI regression test for InteractiveGizmo (FreeCAD 1.1.1 + xvfb).

Run from repo root:
  xvfb-run -a timeout 60 tools/squashfs-root/AppRun tools/gizmo_gui_test.py
  # or with extracted AppImage at tools/squashfs-root/
"""

open("/workspace/tools/gizmo_heartbeat.txt", "w").write("script_started\n")

import traceback
import FreeCAD as App
import FreeCADGui as Gui

open("/workspace/tools/gizmo_heartbeat.txt", "a").write(f"GuiUp={App.GuiUp}\n")

try:
    doc = App.newDocument("T")
    import Part

    box = doc.addObject("Part::Box", "Box")
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, box.Name)
    open("/workspace/tools/gizmo_heartbeat.txt", "a").write("box_ready\n")

    with open("/workspace/macros/InteractiveGizmo.FCMacro", encoding="utf-8") as handle:
        source = handle.read().replace("GizmoManager.instance().toggle()", "pass")
    namespace = {}
    exec(compile(source, "macro", "exec"), namespace)
    open("/workspace/tools/gizmo_heartbeat.txt", "a").write("macro_executed\n")

    mgr = namespace["GizmoManager"].instance()
    mgr.attach(box, silent=True)
    open("/workspace/tools/gizmo_heartbeat.txt", "a").write(
        f"manual_attach active={mgr.is_active} scene={mgr.view.getSceneGraph().findChild(mgr.annotation)}\n"
    )
    mgr.detach()

    mgr.enable_auto_mode()
    open("/workspace/tools/gizmo_heartbeat.txt", "a").write(
        f"auto_attach active={mgr.is_active}\n"
    )
    mgr.disable_auto_mode()
    mgr.detach()
    open("/workspace/tools/gizmo_heartbeat.txt", "a").write("TEST_OK\n")
except Exception:
    open("/workspace/tools/gizmo_heartbeat.txt", "a").write(traceback.format_exc())

import os

os._exit(0)
