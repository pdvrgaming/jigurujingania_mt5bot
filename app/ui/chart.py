import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFileDialog, QMessageBox
from PySide6.QtCharts import QChart, QChartView, QCandlestickSeries, QCandlestickSet, QDateTimeAxis, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter

class ChartUI(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        
        self.btn_load = QPushButton("Load CSV Data")
        self.btn_load.clicked.connect(self.load_data)
        layout.addWidget(self.btn_load)
        
        self.chart = QChart()
        self.chart.setTitle("Candlestick Chart")
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(self.chart_view.renderHints() | QPainter.RenderHint.Antialiasing) # Anti-aliasing
        layout.addWidget(self.chart_view)
        
        self.setLayout(layout)
        
    def load_data(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not filepath:
            return
            
        try:
            df = pd.read_csv(filepath)
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
            elif 'timestamp' in df.columns:
                df['time'] = pd.to_datetime(df['timestamp'])
                
            series = QCandlestickSeries()
            series.setName("Candles")
            series.setIncreasingColor(Qt.green)
            series.setDecreasingColor(Qt.red)
            
            # Show up to 100 candles to keep it clean
            df_slice = df.tail(100)
            
            for _, row in df_slice.iterrows():
                # QDateTime expects milliseconds since epoch
                ts = int(row['time'].timestamp() * 1000)
                candle = QCandlestickSet(row['open'], row['high'], row['low'], row['close'], ts)
                series.append(candle)
                
            self.chart.removeAllSeries()
            for axis in self.chart.axes():
                self.chart.removeAxis(axis)
                
            self.chart.addSeries(series)
            
            # Axes
            axisX = QDateTimeAxis()
            axisX.setFormat("MM-dd HH:mm")
            axisX.setTitleText("Time")
            self.chart.addAxis(axisX, Qt.AlignBottom)
            series.attachAxis(axisX)
            
            axisY = QValueAxis()
            axisY.setTitleText("Price")
            self.chart.addAxis(axisY, Qt.AlignLeft)
            series.attachAxis(axisY)
            
            # Set ranges
            axisX.setRange(
                df_slice.iloc[0]['time'].to_pydatetime(), 
                df_slice.iloc[-1]['time'].to_pydatetime()
            )
            axisY.setRange(df_slice['low'].min() * 0.999, df_slice['high'].max() * 1.001)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load chart: {e}")
