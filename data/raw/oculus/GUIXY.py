import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd

# Generalized sample data
data = {
    'Time': range(100),  # Example time data
    'HandX': [i * 0.01 for i in range(100)],  # Example HandX data
    'HandY': [i * 0.02 for i in range(100)],  # Example HandY data
    'HandZ': [i * 0.03 for i in range(100)]   # Example HandZ data
}

# Create a DataFrame
df = pd.DataFrame(data)

class HandDataPlotter(tk.Tk):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.title("Hand Data Plotter")
        self.geometry("800x600")

        self.current_index = 0

        # Create figure and axes
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Add scrollbar
        self.scrollbar = ttk.Scale(self, from_=0, to=len(self.data)-1, orient=tk.HORIZONTAL, command=self.update_plot)
        self.scrollbar.pack(fill=tk.X)

        # Initial plot
        self.plot_data(self.current_index)

    def plot_data(self, index):
        self.ax.clear()
        self.ax.scatter(self.data['HandX'][index], self.data['HandY'][index])
        self.ax.set_xlim(min(self.data['HandX']), max(self.data['HandX']))
        self.ax.set_ylim(min(self.data['HandY']), max(self.data['HandY']))
        self.ax.set_title(f"Time: {self.data['Time'][index]}")
        self.ax.set_xlabel('HandX')
        self.ax.set_ylabel('HandY')
        self.canvas.draw()

    def update_plot(self, val):
        self.current_index = int(float(val))
        self.plot_data(self.current_index)

if __name__ == "__main__":
    app = HandDataPlotter(df)
    app.mainloop()
