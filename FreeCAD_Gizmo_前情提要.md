# FreeCAD 交互手柄插件 —— 开发前情提要 (Handoff)

> 这份文档是从另一个会话里整理出来的交接说明。目标是在 **fork 的 FreeCAD 仓库**（或作为独立 Addon/宏）里，开发一个「类 Shapr3D 的交互式拖拽/旋转手柄」功能。把这份 `.md` 放到 fork 仓库根目录，新会话读它即可无缝接手。

---

## 0. 一句话目标

> **选中一个实体 / 草图 / 对象后，自动（或按键）在它身上显示可用鼠标拖动的「平移箭头 + 旋转环」手柄；拖动后把变换实时写回该对象的 `Placement`。**
>
> **当前阶段：先做「不带吸附」的最小可用版本 (v1)。** 平面/面吸附留到 v2。

---

## 1. 背景 & 用户画像

- 用户从 **Shapr3D / Cinema4D** 转过来，已经会用 FreeCAD 基本流程（草图 → Pad 拉伸 → 倒角 → 导出 STL），主要用途是 **3D 打印**。
- 用户**有编程基础**，能接受写 Python。
- 痛点：FreeCAD 自带的移动/装配操作「太呆」——
  - 标准模式下移动物体要「选中 → 调出 `编辑→变换 (Std_TransformManip)` / 改 `Placement` 属性」，没有常驻的、选中即出现的 gizmo。
  - 自带的 `Transform` 手柄试过了，**体验不好**，所以决定自己做。
- 环境：**FreeCAD 1.1.1**，Windows，导航样式用 **MayaGesture**（Alt+左旋转 / Alt+中平移 / 滚轮缩放）。

---

## 2. 为什么要自己做（已调研的现成方案，供参考别重复踩坑）

| 现成方案                           | 能做什么                                 | 为什么不够                                  |
| ------------------------------ | ------------------------------------ | -------------------------------------- |
| `编辑 → 变换 (Std_TransformManip)` | Coin3D 自带的箭头+旋转球手柄                   | 要手动调出、体验差（用户已否决）                       |
| **Assembly 工作台**               | 可鼠标自由拖零件，Joint 支持贴合/同轴/对齐平面（=部分「吸附」） | 偏装配语义，不是想要的「随手拖任意对象」手感；但 **v2 吸附可借鉴它** |
| `Draft.Snapper`（Draft 捕捉系统）    | 端点/中点/面/工作平面捕捉                       | 本身不是手柄；**v2 实现吸附时应复用它，别重写**            |

**结论**：v1 自己写手柄；v2 的吸附优先复用 `Draft.Snapper` / 借鉴 Assembly，不要从零造几何推断。

---

## 3. 技术架构（关键拼图）

FreeCAD 的 3D 视图基于 **Coin3D / Open Inventor**，Python 端通过 **pivy** 操作场景图。

### 拼图 A：监听选择变化（决定何时显示/移除手柄）

```python
import FreeCAD as App
import FreeCADGui as Gui

class GizmoSelectionObserver:
    def addSelection(self, doc, obj_name, sub, pnt):
        obj = App.getDocument(doc).getObject(obj_name)
        GizmoManager.attach(obj)        # 选中 → 挂手柄

    def clearSelection(self, doc):
        GizmoManager.detach()           # 清空选择 → 移除手柄

# 注册：Gui.Selection.addObserver(GizmoSelectionObserver())
# 注销：Gui.Selection.removeObserver(...)
```

### 拼图 B：在选中对象上挂 Coin3D 手柄（dragger / manip）

```python
from pivy import coin

view = Gui.ActiveDocument.ActiveView
sg = view.getSceneGraph()

# 候选手柄：
#   coin.SoTransformerManip()  -> 平移+旋转+缩放（功能全，但视觉较杂）
#   coin.SoJackDragger()       -> 三轴平移+旋转
#   coin.SoCenterballManip()   -> 旋转为主
# v1 建议先用 SoTransformerManip 或自定义只保留平移+旋转
manip = coin.SoTransformerManip()
sg.addChild(manip)
```

> 注意：手柄要放到对象当前 `Placement` 的位置（用对象包围盒中心或 `Placement.Base` 初始化 `manip` 的 translation/rotation）。

### 拼图 C：拖动回调 → 写回 `Placement`

```python
def on_motion(user_data, dragger_sensor):
    trans = manip.translation.getValue().getValue()      # (x, y, z)
    rot   = manip.rotation.getValue().getValue()          # 四元数 (x,y,z,w)
    obj.Placement = App.Placement(
        App.Vector(*trans),
        App.Rotation(rot[0], rot[1], rot[2], rot[3]),
    )

manip.addValueChangedCallback(on_motion)   # 具体回调注册方式按 pivy 版本调整
```

### 拼图 D（v2，暂不做）：吸附

- 拖动中遍历场景里其它实体的**平面面 (planar Face)**，取平面方程；
- 计算被拖对象的某个参考面到目标面的**距离 / 夹角**，落入阈值就把 `Placement` 对齐过去；
- **优先复用 `Draft.Snapper`** 拿面/点捕捉，减少自写几何。

### 拼图 E：打包

- **先做成宏 (`.FCMacro`)** 快速验证（最快迭代）。
- 跑通后再封装成 **Addon / 自定义工作台**：`InitGui.py`（注册工作台 + 命令）+ 命令类（`Activated` / `GetResources`）。

---

## 4. v1 验收标准（这次要做的）

1. 在 FreeCAD 里选中一个实体（如之前做的 Body/Pad），手柄出现在它身上。
2. 鼠标拖动**平移箭头** → 物体跟着移动；松手后 `Placement` 被正确写入（模型树/属性面板能看到数值变化，且可撤销 Undo）。
3. 拖动**旋转环** → 物体旋转，同样写回 `Placement`。
4. 取消选择 / 选别的对象 → 旧手柄移除，新对象上出现手柄。
5. **不需要**吸附、不需要推拉(Push/Pull)、不需要多选。

### 待用户拍板的设计决策（开发前确认）

- **触发方式**：
  - 选项 1（更像 Shapr3D）：**选中即自动显示**手柄（用拼图 A 的 observer）。
  - 选项 2（更易调试、不晃眼）：**按快捷键 / 点工具栏按钮**对当前选中对象显示手柄。
  - > 建议：**v1 先做选项 2**（命令触发）跑通核心逻辑，再升级成选项 1 自动显示。
- 旋转中心：用**包围盒中心**还是 `Placement.Base`？（建议包围盒中心，手感更直观。）

---

## 5. 路线图

- **v1**：命令触发的平移+旋转手柄，写回 `Placement`（本次目标）
- v1.1：改成「选中自动显示 / 取消自动移除」（observer）
- v1.2：旋转中心 = 包围盒中心；手柄尺寸自适应对象大小
- v2：吸附到其它平面（复用 `Draft.Snapper`）
- v2.1：吸附到面/边/点，带视觉高亮提示
- v3（远期，谨慎）：Push/Pull 直接建模、智能推断

---

## 6. 关键参考 / 自查清单

- FreeCAD Python API：`App.Placement`, `App.Vector`, `App.Rotation`
- 选择观察者：`Gui.Selection.addObserver / removeObserver`
- 场景图：`Gui.ActiveDocument.ActiveView.getSceneGraph()`
- Coin3D draggers/manips：`SoTransformerManip` / `SoJackDragger` / `SoCenterballManip`（`from pivy import coin`）
- 捕捉（v2）：`Draft.Snapper`
- 装配参考（v2 吸附逻辑借鉴）：内置 **Assembly 工作台**源码
- 调试技巧：先在 FreeCAD 的 **Python 控制台**逐段跑拼图 A/B/C，确认每块能动，再合成宏。

> ⚠️ pivy 不同版本回调注册 API（`addValueChangedCallback` / `addMotionCallback` / 用 `SoFieldSensor`）略有差异，落地时以 fork 里实际版本为准。

---

## 7. 实现状态（本 fork）

| 文件 | 说明 |
|------|------|
| `macros/InteractiveGizmo.FCMacro` | **v1 宏**：命令触发，平移+旋转，写回 `Placement`，旋转中心=包围盒中心 |
| `src/Gui/Inventor/Draggers/SoTransformDragger.*` | FreeCAD 内置三轴平移+旋转手柄（宏优先复用此节点） |
| `src/Gui/ViewProviderDragger.*` | 内置 `Std_TransformManip` 的实现参考（含 pivot / undo 逻辑） |

### 使用方法

1. 在 FreeCAD 中：**宏 → 宏管理 → 添加** `macros/InteractiveGizmo.FCMacro`（或从文件执行一次以注册命令）。
2. 选中一个带 `Placement` 的对象（Body、Pad、Part 等）。
3. 运行命令 **「交互手柄」**（`InteractiveGizmo_Toggle`），或再次执行宏。
4. 拖动手柄平移/旋转；松手后 **Ctrl+Z** 可撤销。
5. 再运行一次命令可移除手柄。

---

## 8. 下一步（新会话开场可直接说）

> 「按 `FreeCAD_Gizmo_前情提要.md` 的 v1 验收标准，帮我写一个**命令触发**的宏：对当前选中的实体显示平移+旋转手柄，拖动后写回 `Placement`，支持 Undo。旋转中心用包围盒中心。先给我能在 FreeCAD Python 控制台/宏里直接跑的版本。」

**v1 已完成（宏）。** 下一步可做 v1.1：选中自动显示 / 取消自动移除（SelectionObserver）。
