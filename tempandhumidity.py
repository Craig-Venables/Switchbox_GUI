import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

def load_data(base_path):
    """
    Finds all CSV files in subdirectories, and concatenates them into a single DataFrame.
    """
    all_files = glob.glob(os.path.join(base_path, "*", "*.csv"))
    df_list = []
    
    for file in all_files:
        try:
            # We parse the timestamp column as dates
            df = pd.read_csv(file, parse_dates=['timestamp'])
            df_list.append(df)
        except Exception as e:
            print(f"Error reading {file}: {e}")
            
    if not df_list:
        return pd.DataFrame()
        
    full_df = pd.concat(df_list, ignore_index=True)
    
    # Set the timestamp as the index and sort it
    full_df.set_index('timestamp', inplace=True)
    full_df.sort_index(inplace=True)
    
    return full_df

def plot_daily_summary(df, output_path=None):
    """
    Creates a clean, thesis-quality plot showing the daily mean, min, and max
    for both temperature and humidity.
    """
    # Resample the high-frequency data to daily aggregations
    daily_mean = df.resample('D').mean()
    daily_min = df.resample('D').min()
    daily_max = df.resample('D').max()
    
    # Set a clean academic visual style using seaborn
    sns.set_theme(style="ticks", context="paper", font_scale=1.3)
    
    # Create a figure with two subplots sharing the x-axis
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # ---------- Temperature Plot (Top) ----------
    ax1.plot(daily_mean.index, daily_mean['temperature'], color='#d62728', linewidth=2, label='Daily Mean')
    # Fill between min and max
    ax1.fill_between(daily_mean.index, daily_min['temperature'], daily_max['temperature'], 
                     color='#d62728', alpha=0.2, label='Min-Max Range')
    
    ax1.set_ylabel('Temperature (°C)', fontweight='bold')
    ax1.set_title('Lab Temperature and Humidity Dynamics (2026)', pad=15, fontweight='bold', fontsize=14)
    ax1.legend(loc='best', frameon=False)
    ax1.grid(True, axis='y', linestyle='--', alpha=0.7)
    
    # ---------- Humidity Plot (Bottom) ----------
    ax2.plot(daily_mean.index, daily_mean['humidity'], color='#1f77b4', linewidth=2, label='Daily Mean')
    # Fill between min and max
    ax2.fill_between(daily_mean.index, daily_min['humidity'], daily_max['humidity'], 
                     color='#1f77b4', alpha=0.2, label='Min-Max Range')
    
    ax2.set_ylabel('Relative Humidity (%)', fontweight='bold')
    ax2.set_xlabel('Date (Month - Day)', fontweight='bold')
    ax2.legend(loc='best', frameon=False)
    ax2.grid(True, axis='y', linestyle='--', alpha=0.7)
    
    # Formats the X-axis to show dates nicely
    date_form = mdates.DateFormatter("%b")
    ax2.xaxis.set_major_formatter(date_form)
    # Add minor ticks for better day resolution
    ax2.xaxis.set_minor_locator(mdates.DayLocator(interval=7))
    
    # Removes top/right borders to look much cleaner
    sns.despine()
    
    plt.tight_layout()
    
    if output_path:
        # Save as high-resolution image for the thesis
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
        
    plt.show()

if __name__ == "__main__":
    # The path pointing to the 2026 data folders
    data_dir = r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Phd\General\Lab Temp and Humidity\2026"
    
    # Generate an output file path in the parent directory
    parent_dir = os.path.dirname(data_dir)
    output_image = os.path.join(parent_dir, 'temp_humidity_plot_2026.png')
    
    print(f"Searching for CSVs in: {data_dir}...")
    df = load_data(data_dir)
    
    if not df.empty:
        print(f"Successfully loaded {len(df)} total data points across all folders.")
        print("Generating daily summary plot...")
        plot_daily_summary(df, output_path=output_image)
    else:
        print("No CSV data found! Please double-check the path or folder structure.")
