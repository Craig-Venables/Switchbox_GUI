import pandas as pd
import io
import matplotlib.pyplot as plt
import seaborn as sns

data = """
Sample,yield,concentration,polymer,separation
79,3,0.1,3,30.65
80,81,0.1,2,26.44
81,0,0.07,3,35.76
82,80,0.07,2,32.12
83,67,0.05,3,41.49
84,20,0.05,2,36.73
87,5,0.05,3,41.49
89,50,0.05,2,36.73
"""
df = pd.read_csv(io.StringIO(data.strip()))

# Plot 1: Remake Yield by Polymer % with sample number labels
plt.figure(figsize=(6.5, 5.2))
sns.boxplot(data=df, x='polymer', y='yield', palette='Pastel1', width=0.42, zorder=1)
# Use scatterplot or stripplot and annotate each point
# To make annotation easy, we'll plot the points with a scatter plot
# We add a slight jitter to the x-axis so overlapping points (like 83 and 87 if they were overlapping, though they aren't in yield) are clear.
# Actually, let's just plot them at the exact category x-coords but offset the labels slightly.
import numpy as np
np.random.seed(42)

for i, row in df.iterrows():
    # polymer is 2 or 3. Map to x-index: 2 -> 0, 3 -> 1
    x_val = 0 if row['polymer'] == 2 else 1
    # Add a tiny jitter to x for visual clarity
    jitter = np.random.uniform(-0.05, 0.05)
    plt.scatter(x_val + jitter, row['yield'], color='black', edgecolor='white', s=80, zorder=3)
    # Annotate with Sample number
    plt.text(x_val + jitter + 0.06, row['yield'], f"S{int(row['Sample'])}", 
             fontsize=9, verticalalignment='center', zorder=4, fontweight='bold')

plt.title('Yield by Polymer Percentage (with Sample Labels)')
plt.xlabel('Polymer (%)')
plt.ylabel('Yield (%)')
plt.xticks([0, 1], ['2%', '3%'])
plt.grid(True, linestyle='--', alpha=0.4)
plt.xlim(-0.60, 1.60)
plt.ylim(-14, 114)
plt.tight_layout(pad=1.1)
plt.savefig('yield_by_polymer_labeled.png', dpi=150, bbox_inches='tight', pad_inches=0.25)
plt.close()

# Let's think of another cool plot.
# Plot 2: Yield vs Separation. 
# This shows how device performance directly maps to the physical morphology (separation).
plt.figure(figsize=(7, 5))
# Color by polymer % and scale size by concentration
sns.scatterplot(data=df, x='separation', y='yield', hue='polymer', size='concentration', 
                palette='Set1', sizes=(60, 200), alpha=0.8)

# Add labels to every point in this scatter plot
for i, row in df.iterrows():
    plt.text(row['separation'] + 0.5, row['yield'] - 1, f"S{int(row['Sample'])}", 
             fontsize=9, verticalalignment='center', fontweight='bold')

plt.title('Device Yield vs. Internal Phase Separation')
plt.xlabel('Separation (nm)')
plt.ylabel('Yield (%)')
plt.grid(True, linestyle='--', alpha=0.5)
plt.xlim(24, 45)
plt.ylim(-10, 110)
plt.legend(title='Variables', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.savefig('yield_vs_separation.png', dpi=150)
plt.close()

print("Both images saved successfully!")