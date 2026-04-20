# Generated with claude

import plotly.graph_objects as go
from collections import defaultdict
import colorsys
import numpy as np
import json


def generate_html_visualization(cp, design_name, output_html="clustering_visualization.html"):
    """Generate a standalone interactive HTML visualization of clustering.

    Renders clusters, ICN (inter-cluster noise) points, and cluster centers.
    Click an ICN in the browser to see its net connections as red lines.

    Args:
        cp: ClusterParser with loaded positions, nets, and clustering labels.
        design_name: Name of the design (used in the title).
        output_html: Path to write the HTML file.
    """
    i = cp.num_snapshots - 1  # last snapshot
    col_x = i * 2
    col_y = i * 2 + 1

    # --- Gather cluster data ---
    cluster_labels = sorted([l for l in cp.unique_labels if l != -1])
    n_clusters = len(cluster_labels)

    def cluster_color(idx, total):
        h = idx / total
        r, g, b = colorsys.hsv_to_rgb(h, 0.7, 0.85)
        return f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"

    label_to_color = {l: cluster_color(j, n_clusters) for j, l in enumerate(cluster_labels)}

    # --- Build per-node connection data (all cells) ---
    node_connections = defaultdict(set)  # node_id -> set of connected node_ids
    for net in cp.net_nodes:
        node_ids_in_net = []
        for node_id, _, _, _ in net:
            if node_id < len(cp.labels):
                node_ids_in_net.append(node_id)
        for a in node_ids_in_net:
            for b in node_ids_in_net:
                if a != b:
                    node_connections[a].add(b)

    # --- Per-ICN connection data for JS ---
    noise_indices = list(np.where(cp.labels == -1)[0])
    icn_conn_js = {}
    for scatter_idx, node_id in enumerate(noise_indices):
        if node_id in node_connections:
            ix = float(cp.data[node_id, col_x])
            iy = float(cp.data[node_id, col_y])
            lines = []
            for t in node_connections[node_id]:
                tx = float(cp.data[t, col_x])
                ty = float(cp.data[t, col_y])
                lines.append([ix, iy, tx, ty])
            icn_conn_js[str(scatter_idx)] = lines

    icn_positions_js = {}
    for scatter_idx, node_id in enumerate(noise_indices):
        icn_positions_js[str(scatter_idx)] = [
            float(cp.data[node_id, col_x]),
            float(cp.data[node_id, col_y])
        ]

    # --- Per-cluster-cell connection data for JS ---
    # cluster_conn_js[label_str][scatter_idx_str] = list of [x1,y1,x2,y2]
    cluster_conn_js = {}
    cluster_pos_js = {}
    for label in cluster_labels:
        label_indices = list(np.where(cp.labels == label)[0])
        conns = {}
        positions = {}
        for scatter_idx, node_id in enumerate(label_indices):
            positions[str(scatter_idx)] = [
                float(cp.data[node_id, col_x]),
                float(cp.data[node_id, col_y])
            ]
            if node_id in node_connections:
                ix = float(cp.data[node_id, col_x])
                iy = float(cp.data[node_id, col_y])
                lines = []
                for t in node_connections[node_id]:
                    tx = float(cp.data[t, col_x])
                    ty = float(cp.data[t, col_y])
                    lines.append([ix, iy, tx, ty])
                conns[str(scatter_idx)] = lines
        cluster_conn_js[str(label)] = conns
        cluster_pos_js[str(label)] = positions

    # --- Build Plotly traces ---
    fig = go.Figure()

    # Traces 0..N-1: Cluster points
    cluster_trace_start = 0
    for label in cluster_labels:
        mask = cp.labels == label
        fig.add_trace(go.Scattergl(
            x=cp.data[mask, col_x],
            y=cp.data[mask, col_y],
            mode='markers',
            marker=dict(size=2, color=label_to_color[label], opacity=0.85),
            name=f'Cluster {label} ({mask.sum()})',
            hovertemplate='x=%{x:.0f}<br>y=%{y:.0f}<extra>Cluster ' + str(label) + '</extra>',
            showlegend=False,
        ))

    # ICN trace
    icn_trace_idx = cluster_trace_start + n_clusters
    noise_mask = cp.labels == -1
    fig.add_trace(go.Scattergl(
        x=cp.data[noise_mask, col_x],
        y=cp.data[noise_mask, col_y],
        mode='markers',
        marker=dict(size=3, color='black'),
        name=f'ICN ({noise_mask.sum()} cells)',
        hovertemplate='x=%{x:.0f}<br>y=%{y:.0f}<extra>ICN</extra>',
    ))

    # Connection lines (on top of cells)
    line_trace_idx = icn_trace_idx + 1
    fig.add_trace(go.Scattergl(
        x=[], y=[],
        mode='lines',
        line=dict(color='rgba(255,50,50,0.7)', width=1.5),
        hoverinfo='skip',
        name='Connections',
    ))

    # Highlight marker for selected cell (on top of everything)
    highlight_trace_idx = line_trace_idx + 1
    fig.add_trace(go.Scattergl(
        x=[], y=[],
        mode='markers',
        marker=dict(size=12, color='red', symbol='circle'),
        hoverinfo='skip',
        name='Selected cell',
        showlegend=False,
    ))

    fig.update_layout(
        title=f'{design_name} — Click any cell to see its connections',
        xaxis=dict(title='X', scaleanchor='y', scaleratio=1),
        yaxis=dict(title='Y'),
        width=1200, height=1000,
        template='plotly_white',
        legend=dict(itemsizing='constant'),
    )

    # --- Write HTML with JS click handler ---
    config = {'modeBarButtonsToRemove': ['autoScale2d'], 'displaylogo': False}
    html_str = fig.to_html(include_plotlyjs=True, full_html=True, config=config)

    # Build cluster label -> trace index mapping for JS
    cluster_trace_map = {}
    for j, label in enumerate(cluster_labels):
        cluster_trace_map[str(cluster_trace_start + j)] = str(label)

    custom_js = f"""
    <script>
    (function() {{
        var icnConns = {json.dumps(icn_conn_js)};
        var icnPos = {json.dumps(icn_positions_js)};
        var clusterConns = {json.dumps(cluster_conn_js)};
        var clusterPos = {json.dumps(cluster_pos_js)};
        var clusterTraceMap = {json.dumps(cluster_trace_map)};
        var lineTraceIdx = {line_trace_idx};
        var highlightTraceIdx = {highlight_trace_idx};
        var icnPointTrace = {icn_trace_idx};

        var btn = document.createElement('button');
        btn.innerText = 'Reset Selection';
        btn.style.cssText = 'position:fixed;top:12px;right:20px;z-index:9999;padding:8px 16px;font-size:14px;cursor:pointer;background:#e74c3c;color:white;border:none;border-radius:4px;display:none;';
        document.body.appendChild(btn);

        var gd = document.querySelectorAll('.plotly-graph-div')[0];

        function resetSelection() {{
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [lineTraceIdx]);
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [highlightTraceIdx]);
            btn.style.display = 'none';
        }}

        function showConnections(conns, pos, idx) {{
            if (!(idx in conns)) return;
            var lx = [], ly = [];
            conns[idx].forEach(function(seg) {{
                lx.push(seg[0], seg[2], null);
                ly.push(seg[1], seg[3], null);
            }});
            Plotly.restyle(gd, {{x: [lx], y: [ly]}}, [lineTraceIdx]);
            var p = pos[idx];
            Plotly.restyle(gd, {{x: [[p[0]]], y: [[p[1]]]}}, [highlightTraceIdx]);
            btn.style.display = 'block';
        }}

        gd.on('plotly_click', function(data) {{
            var pt = data.points[0];
            var curve = String(pt.curveNumber);
            var idx = String(pt.pointIndex);

            if (pt.curveNumber === icnPointTrace) {{
                showConnections(icnConns, icnPos, idx);
            }} else if (curve in clusterTraceMap) {{
                var label = clusterTraceMap[curve];
                showConnections(clusterConns[label], clusterPos[label], idx);
            }}
        }});

        btn.addEventListener('click', resetSelection);

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                Plotly.relayout(gd, {{'xaxis.autorange': true, 'yaxis.autorange': true}});
            }}
        }});
    }})();
    </script>
    """

    html_str = html_str.replace('</body>', custom_js + '</body>')
    with open(output_html, 'w') as f:
        f.write(html_str)
    n_conns = sum(len(v) for v in node_connections.values())
    print(f"Saved to {output_html}")
    print(f"  {len(node_connections)} cells with connections, {n_conns} total links")
