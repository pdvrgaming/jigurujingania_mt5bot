import json
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QListWidget,
                             QMessageBox, QSplitter, QTextEdit, QFileDialog,
                             QListWidgetItem)
from PySide6.QtCore import Qt
from app.core.config import config
import traceback

class StrategyBuilder(QWidget):
    def __init__(self):
        super().__init__()
        
        self.strat_dir = Path(config.get("data_directory", "data")) / "strategies"
        self.strat_dir.mkdir(parents=True, exist_ok=True)
        
        self.rules = []
        
        main_layout = QVBoxLayout()
        
        splitter = QSplitter(Qt.Horizontal)
        
        # --- LEFT SIDE: Visual Builder ---
        visual_widget = QWidget()
        v_layout = QVBoxLayout()
        
        # Top buttons
        top_btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Strategy")
        self.btn_load.clicked.connect(self.load_strategy)
        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.clicked.connect(self.clear_all)
        top_btn_layout.addWidget(self.btn_load)
        top_btn_layout.addWidget(self.btn_clear)
        v_layout.addLayout(top_btn_layout)
        
        # Header
        h_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Strategy Name")
        self.name_input.textChanged.connect(self.update_json_from_visual)
        
        self.symbol_input = QLineEdit("XAUUSD")
        self.symbol_input.textChanged.connect(self.update_json_from_visual)
        
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["M1", "M5", "M15", "M30", "H1", "H4", "D1"])
        self.timeframe_combo.currentIndexChanged.connect(self.update_json_from_visual)
        
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["BUY", "SELL"])
        self.direction_combo.currentIndexChanged.connect(self.update_json_from_visual)
        
        h_layout.addWidget(QLabel("Name:"))
        h_layout.addWidget(self.name_input)
        h_layout.addWidget(QLabel("Symbol:"))
        h_layout.addWidget(self.symbol_input)
        h_layout.addWidget(QLabel("TF:"))
        h_layout.addWidget(self.timeframe_combo)
        h_layout.addWidget(QLabel("Dir:"))
        h_layout.addWidget(self.direction_combo)
        
        v_layout.addLayout(h_layout)
        
        # Rules List
        v_layout.addWidget(QLabel("RULES"))
        self.rules_list = QListWidget()
        v_layout.addWidget(self.rules_list)
        
        self.btn_delete_rule = QPushButton("Delete Selected Rule")
        self.btn_delete_rule.clicked.connect(self.delete_selected_rule)
        v_layout.addWidget(self.btn_delete_rule)
        
        # Rule Editor
        rule_layout = QHBoxLayout()
        self.left_type = QComboBox()
        self.left_type.addItems(["price", "indicator"])
        self.left_name = QComboBox()
        self.left_name.addItems(["close", "open", "high", "low", "SMA", "EMA", "RSI", "ATR"])
        self.left_period = QLineEdit("14")
        self.left_period.setPlaceholderText("Period")
        
        self.operator = QComboBox()
        self.operator.addItems([">", "<", "==", ">=", "<=", "crosses_above", "crosses_below"])
        
        self.right_type = QComboBox()
        self.right_type.addItems(["price", "indicator", "constant"])
        self.right_name = QComboBox()
        self.right_name.addItems(["close", "open", "high", "low", "SMA", "EMA", "RSI", "ATR"])
        self.right_period = QLineEdit("14")
        self.right_period.setPlaceholderText("Period/Value")
        
        rule_layout.addWidget(self.left_type)
        rule_layout.addWidget(self.left_name)
        rule_layout.addWidget(self.left_period)
        rule_layout.addWidget(self.operator)
        rule_layout.addWidget(self.right_type)
        rule_layout.addWidget(self.right_name)
        rule_layout.addWidget(self.right_period)
        
        self.btn_add_rule = QPushButton("+ Add Rule")
        self.btn_add_rule.clicked.connect(self.add_rule)
        rule_layout.addWidget(self.btn_add_rule)
        
        v_layout.addLayout(rule_layout)
        
        # Logic operator
        logic_layout = QHBoxLayout()
        logic_layout.addWidget(QLabel("Combine rules with:"))
        self.logic_op = QComboBox()
        self.logic_op.addItems(["AND", "OR"])
        self.logic_op.currentIndexChanged.connect(self.update_json_from_visual)
        logic_layout.addWidget(self.logic_op)
        logic_layout.addStretch()
        v_layout.addLayout(logic_layout)
        
        visual_widget.setLayout(v_layout)
        
        # --- RIGHT SIDE: Raw JSON Editor ---
        json_widget = QWidget()
        j_layout = QVBoxLayout()
        j_layout.addWidget(QLabel("RAW JSON (Fields to Speak)"))
        self.json_editor = QTextEdit()
        self.json_editor.setStyleSheet("font-family: monospace;")
        
        self.btn_sync_visual = QPushButton("Sync Visual UI from JSON")
        self.btn_sync_visual.clicked.connect(self.sync_from_json)
        
        j_layout.addWidget(self.json_editor)
        j_layout.addWidget(self.btn_sync_visual)
        json_widget.setLayout(j_layout)
        
        splitter.addWidget(visual_widget)
        splitter.addWidget(json_widget)
        
        main_layout.addWidget(splitter)
        
        # Save
        self.btn_save = QPushButton("Save Strategy")
        self.btn_save.clicked.connect(self.save_strategy)
        main_layout.addWidget(self.btn_save)
        
        self.setLayout(main_layout)
        
        # Initialize default state
        self.update_json_from_visual()
        
    def add_rule(self):
        left = {"type": self.left_type.currentText(), "name": self.left_name.currentText()}
        if self.left_type.currentText() == "indicator":
            try: left["period"] = int(self.left_period.text())
            except ValueError: left["period"] = 14
            
        right = {"type": self.right_type.currentText()}
        if self.right_type.currentText() == "indicator":
            right["name"] = self.right_name.currentText()
            try: right["period"] = int(self.right_period.text())
            except ValueError: right["period"] = 14
        elif self.right_type.currentText() == "price":
            right["name"] = self.right_name.currentText()
        else: # constant
            try: right["value"] = float(self.right_period.text())
            except ValueError: right["value"] = 0.0
            
        rule = {
            "left": left,
            "operator": self.operator.currentText(),
            "right": right
        }
        self.rules.append(rule)
        self.refresh_rules_list()
        self.update_json_from_visual()
        
    def delete_selected_rule(self):
        idx = self.rules_list.currentRow()
        if 0 <= idx < len(self.rules):
            self.rules.pop(idx)
            self.refresh_rules_list()
            self.update_json_from_visual()
            
    def clear_all(self):
        self.name_input.clear()
        self.symbol_input.setText("XAUUSD")
        self.rules = []
        self.refresh_rules_list()
        self.update_json_from_visual()
        
    def refresh_rules_list(self):
        self.rules_list.clear()
        for r in self.rules:
            left_str = f"[{r['left'].get('name', '')} {r['left'].get('period', '')}]"
            right_str = f"[{r['right'].get('name', '')} {r['right'].get('period', r['right'].get('value', ''))}]"
            self.rules_list.addItem(f"{left_str} {r['operator']} {right_str}")
            
    def generate_dict(self):
        return {
            "name": self.name_input.text().strip(),
            "version": 1,
            "symbol": self.symbol_input.text(),
            "timeframe": self.timeframe_combo.currentText(),
            "direction": self.direction_combo.currentText(),
            "conditions": {
                "operator": self.logic_op.currentText(),
                "rules": self.rules
            }
        }
        
    def update_json_from_visual(self):
        strat = self.generate_dict()
        self.json_editor.setPlainText(json.dumps(strat, indent=4))
        
    def sync_from_json(self):
        try:
            strat = json.loads(self.json_editor.toPlainText())
            self.name_input.setText(strat.get("name", ""))
            self.symbol_input.setText(strat.get("symbol", "XAUUSD"))
            self.timeframe_combo.setCurrentText(strat.get("timeframe", "M15"))
            self.direction_combo.setCurrentText(strat.get("direction", "BUY"))
            
            cond = strat.get("conditions", {})
            self.logic_op.setCurrentText(cond.get("operator", "AND"))
            self.rules = cond.get("rules", [])
            self.refresh_rules_list()
        except Exception as e:
            QMessageBox.warning(self, "Invalid JSON", f"Failed to parse JSON:\n{e}")
            
    def load_strategy(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Strategy", str(self.strat_dir), "JSON Files (*.json)")
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                self.json_editor.setPlainText(content)
                self.sync_from_json()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load file: {e}")
                
    def save_strategy(self):
        try:
            strat = json.loads(self.json_editor.toPlainText())
            name = strat.get("name", "").strip()
            if not name:
                QMessageBox.warning(self, "Error", "Strategy needs a name.")
                return
                
            filepath = self.strat_dir / f"{name}_v1.json"
            v = 1
            while filepath.exists():
                v += 1
                strat["version"] = v
                filepath = self.strat_dir / f"{name}_v{v}.json"
                
            with open(filepath, "w") as f:
                json.dump(strat, f, indent=4)
                
            QMessageBox.information(self, "Saved", f"Strategy saved as version {v}.")
        except Exception as e:
             QMessageBox.warning(self, "Error", f"Fix JSON before saving:\n{e}")
