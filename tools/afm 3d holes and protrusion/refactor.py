import re

with open('comparison.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace("PLOTLY_TEMPLATE = 'plotly_dark'", "TEMPLATES = [('plotly_dark', ''), ('plotly_white', '_light')]")

funcs = ['_plot_roughness_comparison', '_plot_feature_counts', '_plot_feature_density', 
         '_plot_depth_vs_diameter', '_plot_stats_overview']
for func in funcs:
    text = text.replace(f"def {func}(summary_df, labels, colours, out_dir):", f"def {func}(summary_df, labels, colours, out_dir, template, suffix):")

text = text.replace("def _plot_surface_coverage(summary_df, labels, out_dir):", "def _plot_surface_coverage(summary_df, labels, out_dir, template, suffix):")
text = text.replace("def _plot_ranking_table(summary_df, labels, out_dir):", "def _plot_ranking_table(summary_df, labels, out_dir, template, suffix):")
text = text.replace("def _plot_box_by_sample(df, col, ylabel, labels, colours, stem, out_dir):", "def _plot_box_by_sample(df, col, ylabel, labels, colours, stem, out_dir, template, suffix):")

text = text.replace("template=PLOTLY_TEMPLATE", "template=template")

text = re.sub(r"fig\.write_html\(os\.path\.join\(out_dir, '([^']+)\.html'\)\)", r"fig.write_html(os.path.join(out_dir, f'\1{suffix}.html'))", text)
text = re.sub(r"fig\.write_image\(os\.path\.join\(out_dir, '([^']+)\.png'\)", r"fig.write_image(os.path.join(out_dir, f'\1{suffix}.png')", text)
text = re.sub(r"_save_txt\(os\.path\.join\(out_dir, '([^']+)\.txt'\)", r"if not suffix: _save_txt(os.path.join(out_dir, '\1.txt')", text)

with open('comparison.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Refactored comparison.py')
