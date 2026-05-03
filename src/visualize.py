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

    # --- Node type label helper ---
    _TYPE_LABELS = {0: "Standard Cell", 1: "Macro", 2: "Terminal", 3: "Cluster", -1: "ICN Node"}
    has_cell_refs = hasattr(cp, 'node_cell_refs') and len(cp.node_cell_refs) == len(cp.node_names)
    has_extra = hasattr(cp, 'node_extra') and len(cp.node_extra) == len(cp.node_names)

    def _node_info(node_id):
        name = cp.node_names[node_id] if node_id < len(cp.node_names) else str(node_id)
        ntype = cp.node_type[node_id] if node_id < len(cp.node_type) else 0
        type_label = _TYPE_LABELS.get(ntype, "Unknown")
        cell_ref = (cp.node_cell_refs[node_id] if has_cell_refs and node_id < len(cp.node_cell_refs) else "")
        extra = (cp.node_extra[node_id] if has_extra and node_id < len(cp.node_extra) else "")
        return {"name": name, "type": type_label, "ref": cell_ref, "extra": extra}

    # --- Per-ICN connection data for JS ---
    noise_indices = list(np.where(cp.labels == -1)[0])
    icn_conn_js = {}
    icn_info_js = {}
    for scatter_idx, node_id in enumerate(noise_indices):
        icn_info_js[str(scatter_idx)] = _node_info(node_id)
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
    cluster_info_js = {}
    for label in cluster_labels:
        label_indices = list(np.where(cp.labels == label)[0])
        conns = {}
        positions = {}
        infos = {}
        for scatter_idx, node_id in enumerate(label_indices):
            positions[str(scatter_idx)] = [
                float(cp.data[node_id, col_x]),
                float(cp.data[node_id, col_y])
            ]
            infos[str(scatter_idx)] = _node_info(node_id)
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
        cluster_info_js[str(label)] = infos

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
        var icnInfo = {json.dumps(icn_info_js)};
        var clusterConns = {json.dumps(cluster_conn_js)};
        var clusterPos = {json.dumps(cluster_pos_js)};
        var clusterInfo = {json.dumps(cluster_info_js)};
        var clusterTraceMap = {json.dumps(cluster_trace_map)};
        var lineTraceIdx = {line_trace_idx};
        var highlightTraceIdx = {highlight_trace_idx};
        var icnPointTrace = {icn_trace_idx};

        var btn = document.createElement('button');
        btn.innerText = 'Reset Selection';
        btn.style.cssText = 'position:fixed;top:12px;right:20px;z-index:9999;padding:8px 16px;font-size:14px;cursor:pointer;background:#e74c3c;color:white;border:none;border-radius:4px;display:none;';
        document.body.appendChild(btn);

        // Info panel
        var panel = document.createElement('div');
        panel.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;background:rgba(255,255,255,0.96);border:1px solid #ccc;border-radius:6px;padding:12px 16px;font-family:monospace;font-size:13px;min-width:200px;max-width:340px;box-shadow:0 2px 8px rgba(0,0,0,0.18);display:none;line-height:1.6;';
        document.body.appendChild(panel);

        var gd = document.querySelectorAll('.plotly-graph-div')[0];

        function showPanel(info, clusterLabel) {{
            var html = '';
            html += '<b style="font-size:14px;">' + (info.name || '—') + '</b><br>';
            html += '<span style="color:#555;">Type:&nbsp;</span><b>' + (info.type || '—') + '</b><br>';
            if (info.ref) {{
                html += '<span style="color:#555;">Cell ref:&nbsp;</span>' + info.ref + '<br>';
            }}
            if (info.extra) {{
                html += '<span style="color:#555;">Details:&nbsp;</span>' + info.extra + '<br>';
            }}
            if (clusterLabel !== null) {{
                html += '<span style="color:#555;">Cluster:&nbsp;</span>' + clusterLabel + '<br>';
            }} else {{
                html += '<span style="color:#555;">Cluster:&nbsp;</span><i>ICN (noise)</i><br>';
            }}
            panel.innerHTML = html;
            panel.style.display = 'block';
        }}

        function resetSelection() {{
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [lineTraceIdx]);
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [highlightTraceIdx]);
            btn.style.display = 'none';
            panel.style.display = 'none';
        }}

        function showConnections(conns, pos, idx) {{
            if (!(idx in conns)) {{
                Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [lineTraceIdx]);
                return;
            }}
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
                var info = icnInfo[idx] || {{}};
                showPanel(info, null);
            }} else if (curve in clusterTraceMap) {{
                var label = clusterTraceMap[curve];
                showConnections(clusterConns[label], clusterPos[label], idx);
                var info = (clusterInfo[label] && clusterInfo[label][idx]) ? clusterInfo[label][idx] : {{}};
                showPanel(info, label);
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


def generate_path_visualization(cp, design_name, output_html="path_visualization.html", max_net_degree=None):
    """Generate a standalone interactive HTML visualization for shortest-path exploration.

    Click two cells to find and draw the shortest path (by hop count) between them.
    Path nodes are rendered on top of the path line.

    Args:
        cp: ClusterParser with loaded positions, nets, and clustering labels.
        design_name: Name of the design (used in the title).
        output_html: Path to write the HTML file.
        max_net_degree: Skip nets with more pins than this. None (default) includes all nets.
    """
    i = cp.num_snapshots - 1
    col_x = i * 2
    col_y = i * 2 + 1
    n_placed = cp.data.shape[0]

    # --- Cluster setup ---
    cluster_labels = sorted([l for l in cp.unique_labels if l != -1])
    n_clusters = len(cluster_labels)

    def cluster_color(idx, total):
        h = idx / total
        r, g, b = colorsys.hsv_to_rgb(h, 0.7, 0.85)
        return f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"

    label_to_color = {l: cluster_color(j, n_clusters) for j, l in enumerate(cluster_labels)}

    # --- Build adjacency list (skip high-fanout nets) ---
    path_adj = defaultdict(set)
    skipped_nets = 0
    for net in cp.net_nodes:
        node_ids = [nid for nid, _, _, _ in net if nid < n_placed]
        if max_net_degree is not None and len(node_ids) > max_net_degree:
            skipped_nets += 1
            continue
        for a in node_ids:
            for b in node_ids:
                if a != b:
                    path_adj[a].add(b)

    adj_js = {str(k): list(v) for k, v in path_adj.items()}

    # --- Node cluster membership ---
    node_cluster = {}
    for label in cluster_labels:
        for nid in np.where(cp.labels == label)[0]:
            node_cluster[int(nid)] = int(label)
    noise_indices = list(np.where(cp.labels == -1)[0])
    for nid in noise_indices:
        node_cluster[int(nid)] = -1

    # --- Parallel node data arrays (indexed by global node_id) ---
    has_cell_refs = hasattr(cp, 'node_cell_refs') and len(cp.node_cell_refs) == len(cp.node_names)
    has_extra = hasattr(cp, 'node_extra') and len(cp.node_extra) == len(cp.node_names)

    node_names_js = []
    node_type_js = []       # integer: 0=StdCell, 1=Macro, 2=Terminal
    node_cluster_js = []    # cluster label, -1 for ICN, -2 if unknown
    node_cell_refs_js = []
    node_extra_js = []

    for node_id in range(n_placed):
        node_names_js.append(cp.node_names[node_id] if node_id < len(cp.node_names) else str(node_id))
        node_type_js.append(int(cp.node_type[node_id]) if node_id < len(cp.node_type) else 0)
        node_cluster_js.append(int(node_cluster.get(node_id, -2)))
        node_cell_refs_js.append(cp.node_cell_refs[node_id] if has_cell_refs and node_id < len(cp.node_cell_refs) else "")
        node_extra_js.append(cp.node_extra[node_id] if has_extra and node_id < len(cp.node_extra) else "")

    node_x_js = [float(cp.data[k, col_x]) for k in range(n_placed)]
    node_y_js = [float(cp.data[k, col_y]) for k in range(n_placed)]

    # --- Trace indices (order = z-order: higher index = on top) ---
    # 0:               path lines        (bottom — below all cells)
    # 1..n_clusters:   cluster traces
    # n_clusters+1:    ICN trace
    # n_clusters+2:    path node circles (above cells, below stars)
    # n_clusters+3:    Node A star       (top)
    # n_clusters+4:    Node B star       (top)
    path_lines_trace_idx = 0
    cluster_trace_start  = 1
    icn_trace_idx        = cluster_trace_start + n_clusters
    path_nodes_trace_idx = icn_trace_idx + 1
    node_a_trace_idx     = icn_trace_idx + 2
    node_b_trace_idx     = icn_trace_idx + 3

    # --- Trace -> node ID mapping ---
    trace_node_ids = {}
    for j, label in enumerate(cluster_labels):
        ids = list(np.where(cp.labels == label)[0])
        trace_node_ids[cluster_trace_start + j] = [int(x) for x in ids]
    trace_node_ids[icn_trace_idx] = [int(x) for x in noise_indices]

    # --- Build Plotly figure ---
    fig = go.Figure()

    # Path edges — index 0, rendered first = below everything
    fig.add_trace(go.Scattergl(
        x=[], y=[],
        mode='lines',
        line=dict(color='rgba(30,120,255,0.8)', width=2),
        hoverinfo='skip',
        name='Shortest path',
        showlegend=False,
    ))

    for label in cluster_labels:
        mask = cp.labels == label
        nids = np.where(mask)[0]
        fig.add_trace(go.Scattergl(
            x=cp.data[mask, col_x],
            y=cp.data[mask, col_y],
            mode='markers',
            marker=dict(size=2, color=label_to_color[label], opacity=0.85),
            name=f'Cluster {label} ({mask.sum()})',
            hovertemplate='<b>%{customdata}</b><br>x=%{x:.0f}, y=%{y:.0f}<extra>Cluster ' + str(label) + '</extra>',
            customdata=[cp.node_names[nid] if nid < len(cp.node_names) else str(nid) for nid in nids],
            showlegend=False,
        ))

    noise_mask = cp.labels == -1
    fig.add_trace(go.Scattergl(
        x=cp.data[noise_mask, col_x],
        y=cp.data[noise_mask, col_y],
        mode='markers',
        marker=dict(size=3, color='black'),
        name=f'ICN ({noise_mask.sum()} cells)',
        hovertemplate='<b>%{customdata}</b><br>x=%{x:.0f}, y=%{y:.0f}<extra>ICN</extra>',
        customdata=[cp.node_names[nid] if nid < len(cp.node_names) else str(nid) for nid in noise_indices],
    ))

    # Path node circles — rendered above all cell dots
    fig.add_trace(go.Scattergl(
        x=[], y=[],
        mode='markers',
        marker=dict(size=8, color='rgba(30,120,255,0.9)', symbol='circle'),
        hoverinfo='skip',
        name='Path nodes',
        showlegend=False,
    ))

    # Node A star — rendered over everything
    fig.add_trace(go.Scattergl(
        x=[], y=[],
        mode='markers+text',
        marker=dict(size=14, color='red', symbol='star'),
        text=['A'], textposition='top center',
        textfont=dict(color='red', size=13, family='Arial Black'),
        hoverinfo='skip',
        name='Start (A)',
        showlegend=False,
    ))

    # Node B star — rendered over everything
    fig.add_trace(go.Scattergl(
        x=[], y=[],
        mode='markers+text',
        marker=dict(size=14, color='#27ae60', symbol='star'),
        text=['B'], textposition='top center',
        textfont=dict(color='#27ae60', size=13, family='Arial Black'),
        hoverinfo='skip',
        name='End (B)',
        showlegend=False,
    ))

    fig.update_layout(
        title=f'{design_name} — Shortest Path Explorer',
        xaxis=dict(title='X', scaleanchor='y', scaleratio=1),
        yaxis=dict(title='Y'),
        width=1200, height=1000,
        template='plotly_white',
        legend=dict(itemsizing='constant'),
    )

    config = {'modeBarButtonsToRemove': ['autoScale2d'], 'displaylogo': False}
    html_str = fig.to_html(include_plotlyjs=True, full_html=True, config=config)

    cluster_trace_map = {str(cluster_trace_start + j): str(label) for j, label in enumerate(cluster_labels)}
    cluster_colors_js = {str(label): color for label, color in label_to_color.items()}

    custom_js = f"""
    <script>
    (function() {{
        var nodeNames    = {json.dumps(node_names_js)};
        var nodeType     = {json.dumps(node_type_js)};
        var nodeCluster  = {json.dumps(node_cluster_js)};
        var nodeCellRefs = {json.dumps(node_cell_refs_js)};
        var nodeExtra    = {json.dumps(node_extra_js)};
        var nodeX        = {json.dumps(node_x_js)};
        var nodeY        = {json.dumps(node_y_js)};
        var nodeAdj      = {json.dumps(adj_js)};
        var traceNodeIds = {json.dumps(trace_node_ids)};
        var clusterTraceMap = {json.dumps(cluster_trace_map)};
        var clusterColors   = {json.dumps(cluster_colors_js)};  // label -> color string
        var ICN_COLOR = 'rgb(0,0,0)';
        var icnTraceIdx     = {icn_trace_idx};
        var pathLinesIdx    = {path_lines_trace_idx};
        var pathNodesIdx    = {path_nodes_trace_idx};
        var nodeAIdx        = {node_a_trace_idx};
        var nodeBIdx        = {node_b_trace_idx};

        var TYPE_LABELS = {{
            "0": "Standard Cell", "1": "Macro", "2": "Terminal", "-1": "ICN Node"
        }};

        var gd = document.querySelectorAll('.plotly-graph-div')[0];
        var selectedA = null, selectedB = null;

        // Status bar (top centre)
        var statusBar = document.createElement('div');
        statusBar.style.cssText = [
            'position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;',
            'background:rgba(255,255,255,0.97);border:1px solid #aaa;border-radius:6px;',
            'padding:9px 20px;font-family:sans-serif;font-size:14px;text-align:center;',
            'box-shadow:0 2px 8px rgba(0,0,0,0.14);min-width:350px;pointer-events:none;'
        ].join('');
        statusBar.innerHTML = '<b>Click a cell to select start (A)</b>';
        document.body.appendChild(statusBar);

        // Info panel (bottom right)
        var infoPanel = document.createElement('div');
        infoPanel.style.cssText = [
            'position:fixed;bottom:20px;right:20px;z-index:9999;',
            'background:rgba(255,255,255,0.97);border:1px solid #ccc;border-radius:6px;',
            'padding:12px 16px;font-family:monospace;font-size:13px;',
            'min-width:220px;max-width:360px;',
            'box-shadow:0 2px 8px rgba(0,0,0,0.18);display:none;line-height:1.7;'
        ].join('');
        document.body.appendChild(infoPanel);

        // Reset button (top right)
        var resetBtn = document.createElement('button');
        resetBtn.innerText = 'Reset (Esc)';
        resetBtn.style.cssText = [
            'position:fixed;top:10px;right:20px;z-index:9999;',
            'padding:8px 16px;font-size:14px;cursor:pointer;',
            'background:#e74c3c;color:white;border:none;border-radius:4px;'
        ].join('');
        document.body.appendChild(resetBtn);

        function getNodeId(curve, ptIdx) {{
            var ids = traceNodeIds[String(curve)];
            return (ids !== undefined) ? ids[ptIdx] : null;
        }}

        function nodeInfoHtml(id, badge, badgeColor) {{
            var name = nodeNames[id] || String(id);
            var tl   = TYPE_LABELS[String(nodeType[id])] || 'Unknown';
            var cl   = nodeCluster[id];
            var clStr = (cl === -1) ? '<i>ICN (noise)</i>' : (cl === -2 ? '—' : String(cl));
            var ref  = nodeCellRefs[id] || '';
            var ex   = nodeExtra[id] || '';
            var h = '<b style="color:' + badgeColor + ';">[' + badge + ']</b> ';
            h += '<b style="font-size:14px;">' + name + '</b><br>';
            h += '<span style="color:#555;">Type:</span> <b>' + tl + '</b><br>';
            if (ref) h += '<span style="color:#555;">Cell ref:</span> ' + ref + '<br>';
            if (ex)  h += '<span style="color:#555;">Details:</span> ' + ex + '<br>';
            h += '<span style="color:#555;">Cluster:</span> ' + clStr;
            return h;
        }}

        // All cell trace indices (clusters + ICN) for opacity control
        var allCellTraceIdxs = Object.keys(traceNodeIds).map(Number);

        function dimCells() {{
            var clusterIdxs = allCellTraceIdxs.filter(function(t) {{ return t !== icnTraceIdx; }});
            if (clusterIdxs.length) Plotly.restyle(gd, {{'marker.opacity': 0.2}}, clusterIdxs);
            Plotly.restyle(gd, {{'marker.opacity': 0.2}}, [icnTraceIdx]);
        }}

        function restoreCells() {{
            var clusterIdxs = allCellTraceIdxs.filter(function(t) {{ return t !== icnTraceIdx; }});
            if (clusterIdxs.length) Plotly.restyle(gd, {{'marker.opacity': 0.85}}, clusterIdxs);
            Plotly.restyle(gd, {{'marker.opacity': 1.0}}, [icnTraceIdx]);
        }}

        function resetAll() {{
            selectedA = null; selectedB = null;
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [pathLinesIdx]);
            Plotly.restyle(gd, {{x: [[]], y: [[]], 'marker.color': [[]]}}, [pathNodesIdx]);
            Plotly.restyle(gd, {{x: [[]], y: [[]], text: [['A']]}}, [nodeAIdx]);
            Plotly.restyle(gd, {{x: [[]], y: [[]], text: [['B']]}}, [nodeBIdx]);
            restoreCells();
            statusBar.innerHTML = '<b>Click a cell to select start (A)</b>';
            infoPanel.style.display = 'none';
        }}

        function bfs(src, dst) {{
            var visited = {{}};
            var prev = {{}};
            var queue = [src];
            visited[src] = true;
            prev[src] = null;
            while (queue.length > 0) {{
                var cur = queue.shift();
                if (cur === dst) {{
                    var path = [];
                    var node = dst;
                    while (node !== null) {{
                        path.unshift(node);
                        node = prev[node];
                    }}
                    return path;
                }}
                var neighbors = nodeAdj[String(cur)] || [];
                for (var i = 0; i < neighbors.length; i++) {{
                    var nb = neighbors[i];
                    if (!visited[nb]) {{
                        visited[nb] = true;
                        prev[nb] = cur;
                        queue.push(nb);
                    }}
                }}
            }}
            return null;
        }}

        function nodeColor(id) {{
            var cl = nodeCluster[id];
            if (cl === -1) return ICN_COLOR;
            var c = clusterColors[String(cl)];
            return c !== undefined ? c : 'rgb(150,150,150)';
        }}

        function drawPath(path) {{
            // Lines trace (rendered first = behind)
            var lx = [], ly = [];
            for (var i = 0; i < path.length; i++) {{
                lx.push(nodeX[path[i]]);
                ly.push(nodeY[path[i]]);
            }}
            Plotly.restyle(gd, {{x: [lx], y: [ly]}}, [pathLinesIdx]);

            // Node circles — colored to match their cluster/ICN color
            var nx = [], ny = [], nc = [];
            for (var i = 0; i < path.length; i++) {{
                nx.push(nodeX[path[i]]);
                ny.push(nodeY[path[i]]);
                nc.push(nodeColor(path[i]));
            }}
            Plotly.restyle(gd, {{x: [nx], y: [ny], 'marker.color': [nc]}}, [pathNodesIdx]);

            // Dim all background cells
            dimCells();
        }}

        function computeAndShowPath() {{
            statusBar.innerHTML = '<b>Computing path\u2026</b>';
            setTimeout(function() {{
                var path = bfs(selectedA, selectedB);
                var nameA = nodeNames[selectedA] || String(selectedA);
                var nameB = nodeNames[selectedB] || String(selectedB);
                var colorA = nodeColor(selectedA);
                var colorB = nodeColor(selectedB);
                if (!path) {{
                    statusBar.innerHTML =
                        '<b style="color:' + colorA + ';">A:</b> ' + nameA + ' \u2192 ' +
                        '<b style="color:' + colorB + ';">B:</b> ' + nameB +
                        ' &nbsp;|&nbsp; <span style="color:#c0392b;"><b>No path found</b></span>';
                    infoPanel.innerHTML =
                        nodeInfoHtml(selectedA, 'A', colorA) +
                        '<hr style="margin:8px 0;">' +
                        nodeInfoHtml(selectedB, 'B', colorB) +
                        '<hr style="margin:8px 0;">' +
                        '<span style="color:#c0392b;"><b>No path found</b></span>';
                    infoPanel.style.display = 'block';
                    return;
                }}
                drawPath(path);
                var hops = path.length - 1;
                var hopStr = hops + ' hop' + (hops !== 1 ? 's' : '');
                var icnCount = 0;
                for (var pi = 1; pi < path.length - 1; pi++) {{
                    if (nodeCluster[path[pi]] === -1) icnCount++;
                }}
                var midNodes = Math.max(path.length - 2, 0);
                var icnPct = midNodes > 0
                    ? (icnCount / midNodes * 100).toFixed(1)
                    : '0.0';
                var icnStr = icnCount + ' / ' + midNodes + ' intermediate nodes are ICN (' + icnPct + '%)';
                statusBar.innerHTML =
                    '<b style="color:' + colorA + ';">A:</b> ' + nameA + ' \u2192 ' +
                    '<b style="color:' + colorB + ';">B:</b> ' + nameB +
                    ' &nbsp;|&nbsp; <b>' + hopStr + '</b>' +
                    ' &nbsp;|&nbsp; ICN: ' + icnCount + '/' + midNodes + ' intermediate (' + icnPct + '%)';
                infoPanel.innerHTML =
                    nodeInfoHtml(selectedA, 'A', colorA) +
                    '<hr style="margin:8px 0;">' +
                    nodeInfoHtml(selectedB, 'B', colorB) +
                    '<hr style="margin:8px 0;">' +
                    '<b>Shortest path: ' + hopStr + ' (' + path.length + ' cells)</b><br>' +
                    '<span style="color:#555;">' + icnStr + '</span>';
                infoPanel.style.display = 'block';
            }}, 10);
        }}

        gd.on('plotly_click', function(data) {{
            if (selectedA !== null && selectedB !== null) return;
            var pt = data.points[0];
            var nodeId = getNodeId(pt.curveNumber, pt.pointIndex);
            if (nodeId === null || nodeId === undefined) return;

            if (selectedA === null) {{
                selectedA = nodeId;
                var colorA = nodeColor(nodeId);
                Plotly.restyle(gd, {{x: [[nodeX[nodeId]]], y: [[nodeY[nodeId]]], 'marker.color': [colorA]}}, [nodeAIdx]);
                Plotly.restyle(gd, {{'textfont.color': [colorA]}}, [nodeAIdx]);
                statusBar.innerHTML =
                    '<b style="color:' + colorA + ';">A:</b> ' + (nodeNames[nodeId] || nodeId) +
                    ' &nbsp;|&nbsp; <b>Now click a cell to select destination (B)</b>';
            }} else if (nodeId !== selectedA) {{
                selectedB = nodeId;
                var colorB = nodeColor(nodeId);
                Plotly.restyle(gd, {{x: [[nodeX[nodeId]]], y: [[nodeY[nodeId]]], 'marker.color': [colorB]}}, [nodeBIdx]);
                Plotly.restyle(gd, {{'textfont.color': [colorB]}}, [nodeBIdx]);
                computeAndShowPath();
            }}
        }});

        resetBtn.addEventListener('click', resetAll);
        document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') resetAll(); }});
    }})();
    </script>
    """

    html_str = html_str.replace('</body>', custom_js + '</body>')
    with open(output_html, 'w') as f:
        f.write(html_str)
    limit_str = f"degree > {max_net_degree}" if max_net_degree is not None else "none"
    print(f"Saved to {output_html}")
    print(f"  {len(path_adj)} nodes in path graph, {skipped_nets} high-fanout nets skipped ({limit_str})")
