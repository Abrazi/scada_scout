import logging
from typing import List, Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem,
    QWidget, QVBoxLayout,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF
)
from PySide6.QtCore import Qt, QRectF, QPointF

from src.core.sfc_parser import SFCNode, SFCAction, SFCTransition

logger = logging.getLogger(__name__)

class SFCVisualizer(QWidget):
    """
    A Sequential Function Chart (SFC) Visualizer Widget.
    Renders states and transitions parsed from Structured Text.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        
        # Style configurations
        self.view.setStyleSheet("QGraphicsView { background-color: #f5f5f5; border: none; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        
        self.nodes: List[SFCNode] = []
        self.node_items: Dict[str, QGraphicsRectItem] = {}
        
    def set_sfc_data(self, nodes: List[SFCNode]):
        """Update the visualizer with new SFC nodes."""
        self.nodes = nodes
        self._render_graph()
        
    def _render_graph(self):
        """Draws the SFC nodes onto the scene."""
        self.scene.clear()
        self.node_items.clear()
        
        if not self.nodes:
            text = self.scene.addText("No SFC states detected in code.\nMake sure you have STATE_... constructs.", QFont("Consolas", 12))
            text.setDefaultTextColor(QColor("#888888"))
            return
            
        # Basic layout parameters
        node_width = 160
        node_height = 60
        x_spacing = 220
        y_spacing = 150
        
        # Determine starting nodes (init nodes)
        init_nodes = [n for n in self.nodes if n.type == 'init']
        if not init_nodes and self.nodes:
            init_nodes = [self.nodes[0]]
            
        # Very simple layout algorithm:
        # Just place nodes in a grid for now. A true graph layout would be ideal, 
        # but for a read-only linear/branching sequential chart, topological sort works best.
        
        # Compute levels based on transitions (BFS)
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
                    queue.append((trans.target, level + 1))
                    
        # Any disconnected nodes go to the bottom
        max_level = max(levels.values()) if levels else 0
        for node in self.nodes:
            if node.id not in levels:
                levels[node.id] = max_level + 1
        
        # Group by levels to assign X positions
        level_groups: Dict[int, List[str]] = {}
        for nid, lvl in levels.items():
            level_groups.setdefault(lvl, []).append(nid)
            
        # Draw nodes
        positions: Dict[str, QPointF] = {}
        
        for lvl in sorted(level_groups.keys()):
            nodes_in_level = level_groups[lvl]
            for i, nid in enumerate(nodes_in_level):
                node = next((n for n in self.nodes if n.id == nid), None)
                if not node: continue
                
                # Center nodes horizontally
                total_width = len(nodes_in_level) * x_spacing
                start_x = -(total_width / 2) + (node_width / 2)
                
                x = start_x + (i * x_spacing)
                y = lvl * y_spacing
                positions[nid] = QPointF(x, y)
                
                self._draw_node(node, x, y, node_width, node_height)
                
        # Draw transitions
        for node in self.nodes:
            if node.id not in positions: continue
            start_pos = positions[node.id]
            
            for trans_idx, trans in enumerate(node.transitions):
                if trans.target not in positions: continue
                end_pos = positions[trans.target]
                self._draw_transition(node.id, trans, start_pos, end_pos, node_width, node_height, trans_idx, len(node.transitions))
                
        # Adjust scene bounds
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
        
    def _draw_node(self, node: SFCNode, x: float, y: float, w: float, h: float):
        """Draw a single SFC step block."""
        is_init = node.type == 'init'
        
        # Main rect
        rect = QGraphicsRectItem(x, y, w, h)
        
        # Colors based on type
        bg_color = QColor("#ffffff")
        border_color = QColor("#333333")
        
        rect.setBrush(QBrush(bg_color))
        
        # Init steps have double borders in IEC 61131-3
        pen = QPen(border_color, 2 if is_init else 1)
        rect.setPen(pen)
        
        if is_init:
            inner_rect = QGraphicsRectItem(x + 4, y + 4, w - 8, h - 8, rect)
            inner_rect.setPen(QPen(border_color, 1))
            
        # Label
        text = QGraphicsTextItem(node.label, rect)
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        text.setFont(font)
        text_rect = text.boundingRect()
        text.setPos(x + (w - text_rect.width()) / 2, y + (h - text_rect.height()) / 2)
        
        # Actions representation (mini box on the right)
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
        self.node_items[node.id] = rect

    def _draw_transition(self, source_id: str, trans: SFCTransition, 
                         start_pos: QPointF, end_pos: QPointF, 
                         node_w: float, node_h: float,
                         sibling_idx: int, total_siblings: int):
        """Draw a sequence line and transition condition."""
        
        path = QPainterPath()
        
        # Start at bottom center of source node
        start_x = start_pos.x() + node_w / 2
        start_y = start_pos.y() + node_h
        
        # End at top center of target node
        end_x = end_pos.x() + node_w / 2
        end_y = end_pos.y()
        
        # For multiple outward transitions, fan them out slightly
        offset = 0
        if total_siblings > 1:
            total_spread = 60
            step = total_spread / (total_siblings - 1)
            offset = - (total_spread / 2) + (sibling_idx * step)
            
        path.moveTo(start_x, start_y)
        
        # Calculate midpoints for orthogonal routing
        mid_y = start_y + (end_y - start_y) / 2
        
        if end_y > start_y:
            # Forward transition
            path.lineTo(start_x, mid_y)
            path.lineTo(end_x, mid_y)
            path.lineTo(end_x, end_y)
        else:
            # Backward loop transition
            path.lineTo(start_x, start_y + 15)
            # Route nicely around the side
            route_x = min(start_x, end_x) - 100 - (sibling_idx * 20)
            path.lineTo(route_x, start_y + 15)
            path.lineTo(route_x, end_y - 15)
            path.lineTo(end_x, end_y - 15)
            path.lineTo(end_x, end_y)

        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(QColor("#333333"), 1.5))
        self.scene.addItem(path_item)
        
        # Draw the target arrow
        arrow_size = 6
        arrow_poly = QPolygonF([
            QPointF(end_x, end_y),
            QPointF(end_x - arrow_size, end_y - arrow_size),
            QPointF(end_x + arrow_size, end_y - arrow_size)
        ])
        arrow = self.scene.addPolygon(arrow_poly, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#333333")))
        
        # Draw transition condition (crossbar and text)
        if end_y > start_y:
            trans_y = mid_y
            trans_x = end_x
        else:
            trans_y = end_y - 15
            trans_x = route_x
            
        crossbar = self.scene.addLine(trans_x - 10, trans_y, trans_x + 10, trans_y, QPen(QColor("#333333"), 2))
        
        # Condition text
        cond_text = trans.condition
        if len(cond_text) > 15:
            cond_text = cond_text[:12] + "..."
            
        text = self.scene.addText(cond_text, QFont("Consolas", 8))
        text_rect = text.boundingRect()
        text.setPos(trans_x + 12, trans_y - text_rect.height() / 2)
        text.setDefaultTextColor(QColor("#0078d4"))
