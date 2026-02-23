import logging
import uuid
from typing import List, Dict, Optional

from PySide6.QtWidgets import (  # type: ignore
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem,
    QWidget, QVBoxLayout, QMenu, QInputDialog, QMessageBox, QDialog,
    QFormLayout, QTextEdit, QDialogButtonBox
)
from PySide6.QtGui import (  # type: ignore
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF,
    QCursor, QAction
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal  # type: ignore

from src.core.sfc_parser import SFCNode, SFCAction, SFCTransition, SFCParser  # type: ignore

logger = logging.getLogger(__name__)

class EditActionsDialog(QDialog):
    def __init__(self, node: SFCNode, parent=None):
        super().__init__(parent)  # type: ignore
        self.setWindowTitle(f"Edit Actions - {node.label}")
        self.resize(500, 300)
        
        layout = QVBoxLayout(self)
        
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 10))
        
        # Format existing actions into ST block
        text = ""
        for action in node.actions:
            time_part = f" T:{action.time}" if action.time else ""
            text += f"(* Q:{action.qualifier}{time_part} *) {action.text};\n"
        
        if not text:
            text = "(* Q:N *) /* Add your code here */;"
            
        self.editor.setPlainText(text)
        layout.addWidget(self.editor)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_actions(self) -> List[SFCAction]:
        text = self.editor.toPlainText()
        # Reparse just the actions using the parser logic
        dummy_code = f"IF state = STATE_DUMMY THEN\n{text}\nEND_IF;"
        nodes = SFCParser.parse(dummy_code)
        if nodes:
             return nodes[0].actions
        return []


class SFCEditor(QWidget):
    """
    Interactive Sequential Function Chart (SFC) Editor Widget.
    Allows for visual creation and editing of steps and transitions.
    """
    
    # Emitted when the user modifies the graph
    graph_changed = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)  # type: ignore
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.view.setStyleSheet("QGraphicsView { background-color: #f5f5f5; border: none; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        
        self.nodes: List[SFCNode] = []
        
        # Custom context menus handled via overriding view events or item events
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._show_context_menu)
        
    def set_sfc_data(self, nodes: List[SFCNode]):
        self.nodes = list(nodes)
        
        # If completely empty, seed with Init step
        if not self.nodes:
             self.nodes.append(SFCNode(
                 id="STATE_INIT",
                 label="INIT",
                 type="init",
                 value=0
             ))
             
        self._render_graph()
        
    def get_sfc_data(self) -> List[SFCNode]:
        return self.nodes
        
    def _notify_change(self):
        """Re-render and emit signal."""
        self._render_graph()
        self.graph_changed.emit(self.nodes)

    def _show_context_menu(self, pos):
        """Show appropriate context menu depending on clicked item."""
        global_pos = self.view.mapToGlobal(pos)
        scene_pos = self.view.mapToScene(pos)
        
        item = self.scene.itemAt(scene_pos, self.view.transform())
        
        menu = QMenu(self)
        
        # If we clicked on a Node (specifically its internal rect, look at parent or data)
        node_id = None
        trans_data = None
        
        if item:
             # Look for node ID in data
             current = item
             while current:
                 if current.data(0) == "node":
                     node_id = current.data(1)
                     break
                 if current.data(0) == "transition":
                     trans_data = current.data(1)
                     break
                 current = current.parentItem()
                 
        if node_id:
            node = next((n for n in self.nodes if n.id == node_id), None)
            if not node: return
            
            action_edit = menu.addAction("Edit Actions...")
            action_add_trans = menu.addAction("Add Transition to New Step...")
            action_add_div = menu.addAction("Add Branch to Existing Step...")
            menu.addSeparator()
            action_del = menu.addAction("Delete Step")
            
            selected = menu.exec(global_pos)
            
            if selected == action_edit:
                self._edit_node_actions(node)
            elif selected == action_add_trans:
                self._add_transition_and_step(node)
            elif selected == action_add_div:
                self._add_branch_to_existing(node)
            elif selected == action_del:
                self._delete_node(node)
                
        elif trans_data:
            # trans_data is a tuple (source_id, trans_index)
            source_id, t_idx = trans_data
            node = next((n for n in self.nodes if n.id == source_id), None)
            if not node: return
            
            action_edit_c = menu.addAction("Edit Condition...")
            action_del_t = menu.addAction("Delete Transition")
            
            selected = menu.exec(global_pos)
            if selected == action_edit_c:
                 self._edit_transition_condition(node, t_idx)
            elif selected == action_del_t:
                 node.transitions.pop(t_idx)
                 self._notify_change()
                 
        else:
             # Clicked empty space
             action_new_init = menu.addAction("Reset Graph (New Init Step)")
             selected = menu.exec(global_pos)
             if selected == action_new_init:
                 self.set_sfc_data([])
                 self._notify_change()

    # --- Actions ---
    
    def _edit_node_actions(self, node: SFCNode):
        dialog = EditActionsDialog(node, self)
        if dialog.exec():
            node.actions = dialog.get_actions()
            self._notify_change()

    def _add_transition_and_step(self, parent_node: SFCNode):
        condition, ok1 = QInputDialog.getText(self, "Transition Condition", "Enter boolean condition (e.g. TRUE, valid := TRUE):", text="TRUE")
        if not ok1: return
        
        step_name, ok2 = QInputDialog.getText(self, "New Step Name", "Enter new step name:")
        if not ok2 or not step_name: return
        
        step_id = f"STATE_{step_name.upper().replace(' ', '_')}"
        if any(n.id == step_id for n in self.nodes):
             QMessageBox.warning(self, "Error", f"Step {step_id} already exists!")
             return
             
        # Find next valid ID
        max_val = max([n.value for n in self.nodes if n.value is not None] + [-1])
        
        # Create Step
        new_node = SFCNode(
            id=step_id,
            label=step_name,
            type='step',
            value=max_val + 1
        )
        self.nodes.append(new_node)
        
        # Create Transition
        parent_node.transitions.append(SFCTransition(
             target=step_id,
             condition=condition,
             priority=len(parent_node.transitions) + 1,
             full_text=f"IF {condition} THEN state := {step_id}; END_IF;",
             line_index=-1,
             block_end_index=-1
        ))
        
        self._notify_change()
        
    def _add_branch_to_existing(self, parent_node: SFCNode):
        condition, ok1 = QInputDialog.getText(self, "Transition Condition", "Enter condition:", text="TRUE")
        if not ok1: return
        
        from PySide6.QtWidgets import QComboBox  # type: ignore
        # Show a combobox dialog for existing steps
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Target Step")
        layout = QVBoxLayout(dialog)
        cb = QComboBox()
        for n in self.nodes:
             if n.id != parent_node.id: # Preclude simple self loops in the UI for now
                  cb.addItem(n.label, n.id)
        layout.addWidget(cb)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
             target_id = cb.currentData()
             if not target_id: return
             
             parent_node.transitions.append(SFCTransition(
                 target=target_id,
                 condition=condition,
                 priority=len(parent_node.transitions) + 1,
                 full_text=f"IF {condition} THEN state := {target_id}; END_IF;",
                 line_index=-1,
                 block_end_index=-1
             ))
             self._notify_change()
             
    def _edit_transition_condition(self, node: SFCNode, t_idx: int):
        trans = node.transitions[t_idx]
        condition, ok = QInputDialog.getText(self, "Edit Condition", "Condition:", text=trans.condition)
        if ok:
             trans.condition = condition
             trans.full_text = f"IF {condition} THEN state := {trans.target}; END_IF;"
             self._notify_change()

    def _delete_node(self, node: SFCNode):
        if len(self.nodes) == 1:
            QMessageBox.warning(self, "Warning", "Cannot delete the last node in the graph.")
            return
            
        # Remove incoming transitions
        for n in self.nodes:
            n.transitions = [t for t in n.transitions if t.target != node.id]
            
        self.nodes.remove(node)
        
        # Reassign initial if deleted
        if node.type == 'init' and self.nodes:
            self.nodes[0].type = 'init'
            
        self._notify_change()
        
    # --- Rendering layout (mirrors SFCVisualizer auto layout) ---
    def _render_graph(self):
        """Draws the SFC nodes onto the scene."""
        self.scene.clear()
        
        if not self.nodes:
            return
            
        node_width = 160
        node_height = 60
        x_spacing = 220
        y_spacing = 150
        
        init_nodes = [n for n in self.nodes if n.type == 'init']
        if not init_nodes and self.nodes:
            init_nodes = [self.nodes[0]]
            
        # BFS Level computation
        levels: Dict[str, int] = {}
        queue = [(n.id, 0) for n in init_nodes]
        visited = set()
        
        while queue:
            node_id, level = queue.pop(0)
            if node_id in levels and levels[node_id] >= level:
                continue
            levels[node_id] = level
            visited.add(node_id)
            
            node = next((n for n in self.nodes if n.id == node_id), None)
            if node:
                for trans in node.transitions:
                    next_level = level + 1  # type: ignore
                    queue.append((trans.target, next_level))
                    
        max_level = max(levels.values()) if levels else 0
        for node in self.nodes:
            if node.id not in levels:
                levels[node.id] = max_level + 1
        
        level_groups: Dict[int, List[str]] = {}
        for nid, lvl in levels.items():
            level_groups.setdefault(lvl, []).append(nid)
            
        positions: Dict[str, QPointF] = {}
        
        for lvl in sorted(level_groups.keys()):
            nodes_in_level = level_groups[lvl]
            for i, nid in enumerate(nodes_in_level):
                node = next((n for n in self.nodes if n.id == nid), None)
                if not node: continue
                
                total_width = len(nodes_in_level) * x_spacing
                start_x = -(total_width / 2) + (node_width / 2)
                
                x = start_x + (i * x_spacing)
                y = lvl * y_spacing
                positions[nid] = QPointF(x, y)
                
                self._draw_node(node, x, y, node_width, node_height)
                
        for node in self.nodes:
            if node.id not in positions: continue
            start_pos = positions[node.id]
            
            for trans_idx, trans in enumerate(node.transitions):  # type: ignore
                if trans.target not in positions: continue
                end_pos = positions[trans.target]
                self._draw_transition(node.id, trans, start_pos, end_pos, node_width, node_height, trans_idx, len(node.transitions))
                
        # Fix Scene bounds
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
        
    def _draw_node(self, node: SFCNode, x: float, y: float, w: float, h: float):
        is_init = node.type == 'init'
        rect = QGraphicsRectItem(x, y, w, h)
        rect.setData(0, "node")
        rect.setData(1, node.id)
        
        bg_color = QColor("#ffffff")
        border_color = QColor("#333333")
        rect.setBrush(QBrush(bg_color))
        rect.setPen(QPen(border_color, 2 if is_init else 1))
        
        if is_init:
            inner_rect = QGraphicsRectItem(x + 4, y + 4, w - 8, h - 8, rect)
            inner_rect.setPen(QPen(border_color, 1))
            
        text = QGraphicsTextItem(node.label, rect)
        text.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        text_rect = text.boundingRect()
        text.setPos(x + (w - text_rect.width()) / 2, y + (h - text_rect.height()) / 2)
        
        if node.actions:
            action_w = 40
            action_box = QGraphicsRectItem(x + w, y + 10, action_w, h - 20, rect)
            action_box.setBrush(QBrush(QColor("#e8f4f8")))
            action_box.setPen(QPen(QColor("#0078d4"), 1))
            
            act_text = QGraphicsTextItem(f"{len(node.actions)}", action_box)
            act_text.setFont(QFont("Segoe UI", 8))
            act_text.setDefaultTextColor(QColor("#0078d4"))
            act_text.setPos(x + w + 10, y + (h - 20 - act_text.boundingRect().height()) / 2 + 10)
            
        self.scene.addItem(rect)

    def _draw_transition(self, source_id: str, trans: SFCTransition, 
                         start_pos: QPointF, end_pos: QPointF, 
                         node_w: float, node_h: float,
                         sibling_idx: int, total_siblings: int):
        
        path = QPainterPath()
        start_x = start_pos.x() + node_w / 2
        start_y = start_pos.y() + node_h
        end_x = end_pos.x() + node_w / 2
        end_y = end_pos.y()
        
        if total_siblings > 1:
            total_spread = 60
            step = total_spread / (total_siblings - 1)
            offset = - (total_spread / 2) + (sibling_idx * step)
        else:
            offset = 0
            
        path.moveTo(start_x, start_y)
        mid_y = start_y + (end_y - start_y) / 2
        
        if end_y > start_y:
            path.lineTo(start_x, mid_y)
            path.lineTo(end_x, mid_y)
            path.lineTo(end_x, end_y)
            trans_y = mid_y
            trans_x = end_x
        else:
            path.lineTo(start_x, start_y + 15)
            route_x = min(start_x, end_x) - 100 - (sibling_idx * 20)
            path.lineTo(route_x, start_y + 15)
            path.lineTo(route_x, end_y - 15)
            path.lineTo(end_x, end_y - 15)
            path.lineTo(end_x, end_y)
            trans_y = end_y - 15
            trans_x = route_x

        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(QColor("#333333"), 1.5))
        
        # Attach data to transition path for context menu targeting
        # (Though we'll attach it to the crossbar/click area realistically)
        path_item.setData(0, "transition")
        path_item.setData(1, (source_id, sibling_idx))
        
        self.scene.addItem(path_item)
        
        arrow_size = 6
        arrow_poly = QPolygonF([
            QPointF(end_x, end_y),
            QPointF(end_x - arrow_size, end_y - arrow_size),
            QPointF(end_x + arrow_size, end_y - arrow_size)
        ])
        self.scene.addPolygon(arrow_poly, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#333333")))
            
        crossbar = self.scene.addLine(trans_x - 10, trans_y, trans_x + 10, trans_y, QPen(QColor("#333333"), 2))
        
        # Make a hidden bounding box over the transition text/crossbar to make it easier to click
        click_box = QGraphicsRectItem(trans_x - 40, trans_y - 15, 80, 30)
        click_box.setPen(QPen(Qt.PenStyle.NoPen))
        click_box.setData(0, "transition")
        click_box.setData(1, (source_id, sibling_idx))
        self.scene.addItem(click_box)
        
        cond_text = trans.condition
        if len(cond_text) > 15:
            cond_text = cond_text[:12] + "..."
            
        text = self.scene.addText(cond_text, QFont("Consolas", 8))
        text_rect = text.boundingRect()
        text.setPos(trans_x + 12, trans_y - text_rect.height() / 2)
        text.setDefaultTextColor(QColor("#0078d4"))
