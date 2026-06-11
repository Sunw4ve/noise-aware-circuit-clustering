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


def generate_module_visualization(cp, design_name, module_csv, output_html="module_visualization.html"):
    """Generate an interactive HTML visualization colored by Verilog module from a CSV.

    Args:
        cp: ClusterParser with loaded positions, nets, and clustering labels.
        design_name: Name of the design (used in the title).
        module_csv: Path to cell_id_map.csv (columns: short_id, hier_name, module, group).
        output_html: Path to write the HTML file.
    """
    import csv as _csv

    i = cp.num_snapshots - 1
    col_x = i * 2
    col_y = i * 2 + 1

    # --- Load module CSV ---
    cell_to_group = {}
    cell_to_module = {}
    cell_to_conf = {}
    with open(module_csv, newline='') as f:
        reader = _csv.DictReader(f)
        for row in reader:
            key = row['short_id']
            cell_to_group[key] = row['group']
            cell_to_module[key] = row['module']
            cell_to_conf[key] = row.get('hier_name', '')

    # Assign group for each node
    UNKNOWN_GROUP = 'unknown'
    node_groups = []
    for node_id in range(len(cp.node_names)):
        name = cp.node_names[node_id] if node_id < len(cp.node_names) else ''
        node_groups.append(cell_to_group.get(name, UNKNOWN_GROUP))

    all_groups = sorted(set(node_groups))
    n_groups = len(all_groups)

    # Distinct color palette per group
    _GROUP_PALETTE = {
        'main_sbox':  'rgb(31,119,180)',
        'kexp_sbox':  'rgb(214,39,40)',
        'key_expand': 'rgb(255,127,14)',
        'top':        'rgb(44,160,44)',
        'rcon':       'rgb(0,200,200)',
        'unknown':    'rgb(180,180,180)',
    }

    def _group_color(idx, total):
        h = idx / max(total, 1)
        r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.88)
        return f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"

    group_to_color = {}
    for j, g in enumerate(all_groups):
        group_to_color[g] = _GROUP_PALETTE.get(g, _group_color(j, n_groups))

    # --- Build per-node connection data ---
    node_connections = defaultdict(set)
    for net in cp.net_nodes:
        ids_in_net = [nid for nid, _, _, _ in net if nid < len(cp.labels)]
        for a in ids_in_net:
            for b in ids_in_net:
                if a != b:
                    node_connections[a].add(b)

    # --- Per-node JS data ---
    has_cell_refs = hasattr(cp, 'node_cell_refs') and len(cp.node_cell_refs) == len(cp.node_names)

    node_info_js = {}
    for node_id in range(len(cp.node_names)):
        name = cp.node_names[node_id] if node_id < len(cp.node_names) else str(node_id)
        node_info_js[str(node_id)] = {
            'name': name,
            'group': node_groups[node_id],
            'module': cell_to_module.get(name, '—'),
            'conf': cell_to_conf.get(name, '—'),
            'ref': (cp.node_cell_refs[node_id] if has_cell_refs and node_id < len(cp.node_cell_refs) else ''),
        }

    # Per-group scatter data for JS click handler
    group_conn_js = {}
    group_pos_js = {}
    group_info_js = {}
    for g in all_groups:
        g_ids = [nid for nid, grp in enumerate(node_groups) if grp == g and nid < len(cp.labels)]
        conns, positions, infos = {}, {}, {}
        for scatter_idx, node_id in enumerate(g_ids):
            positions[str(scatter_idx)] = [float(cp.data[node_id, col_x]), float(cp.data[node_id, col_y])]
            infos[str(scatter_idx)] = node_info_js[str(node_id)]
            if node_id in node_connections:
                ix, iy = float(cp.data[node_id, col_x]), float(cp.data[node_id, col_y])
                lines = []
                for t in node_connections[node_id]:
                    lines.append([ix, iy, float(cp.data[t, col_x]), float(cp.data[t, col_y])])
                conns[str(scatter_idx)] = lines
        group_conn_js[g] = conns
        group_pos_js[g] = positions
        group_info_js[g] = infos

    # --- Build Plotly figure ---
    fig = go.Figure()

    group_trace_map = {}  # trace_index -> group name
    for j, g in enumerate(all_groups):
        mask = np.array([grp == g for grp in node_groups])
        fig.add_trace(go.Scattergl(
            x=cp.data[mask, col_x],
            y=cp.data[mask, col_y],
            mode='markers',
            marker=dict(size=2, color=group_to_color[g], opacity=0.85),
            name=f'{g} ({mask.sum()})',
            hovertemplate='x=%{x:.0f}<br>y=%{y:.0f}<extra>' + g + '</extra>',
        ))
        group_trace_map[str(j)] = g

    # Connection lines trace
    line_trace_idx = len(all_groups)
    fig.add_trace(go.Scattergl(
        x=[], y=[],
        mode='lines',
        line=dict(color='rgba(255,50,50,0.7)', width=1.5),
        hoverinfo='skip',
        name='Connections',
        showlegend=False,
    ))

    # Highlight marker trace
    highlight_trace_idx = line_trace_idx + 1
    fig.add_trace(go.Scattergl(
        x=[], y=[],
        mode='markers',
        marker=dict(size=12, color='red', symbol='circle'),
        hoverinfo='skip',
        name='Selected',
        showlegend=False,
    ))

    fig.update_layout(
        title=f'{design_name} — Colored by Verilog Module | Click any cell to see connections',
        xaxis=dict(title='X', scaleanchor='y', scaleratio=1, autorange=True),
        yaxis=dict(title='Y', autorange=True),
        width=1200, height=1000,
        template='plotly_white',
        legend=dict(itemsizing='constant'),
        uirevision='static',
    )

    config = {'modeBarButtonsToRemove': ['autoScale2d'], 'displaylogo': False}
    html_str = fig.to_html(include_plotlyjs=True, full_html=True, config=config)

    custom_js = f"""
    <script>
    (function() {{
        var groupConns   = {json.dumps(group_conn_js)};
        var groupPos     = {json.dumps(group_pos_js)};
        var groupInfo    = {json.dumps(group_info_js)};
        var groupTraceMap = {json.dumps(group_trace_map)};
        var lineTraceIdx  = {line_trace_idx};
        var hlTraceIdx    = {highlight_trace_idx};

        var gd = document.querySelectorAll('.plotly-graph-div')[0];

        var btn = document.createElement('button');
        btn.innerText = 'Reset Selection';
        btn.style.cssText = 'position:fixed;top:12px;right:20px;z-index:9999;padding:8px 16px;font-size:14px;cursor:pointer;background:#e74c3c;color:white;border:none;border-radius:4px;display:none;';
        document.body.appendChild(btn);

        var panel = document.createElement('div');
        panel.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;background:rgba(255,255,255,0.96);border:1px solid #ccc;border-radius:6px;padding:12px 16px;font-family:monospace;font-size:13px;min-width:220px;max-width:360px;box-shadow:0 2px 8px rgba(0,0,0,0.18);display:none;line-height:1.6;';
        document.body.appendChild(panel);

        function showPanel(info) {{
            var h = '<b style="font-size:14px;">' + (info.name || '—') + '</b><br>';
            h += '<span style="color:#555;">Group:</span> <b>' + (info.group || '—') + '</b><br>';
            h += '<span style="color:#555;">Module:</span> ' + (info.module || '—') + '<br>';
            if (info.conf) h += '<span style="color:#555;">Hier name:</span> ' + info.conf + '<br>';
            if (info.ref) h += '<span style="color:#555;">Cell ref:</span> ' + info.ref + '<br>';
            panel.innerHTML = h;
            panel.style.display = 'block';
        }}

        function reset() {{
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [lineTraceIdx]);
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [hlTraceIdx]);
            btn.style.display = 'none';
            panel.style.display = 'none';
        }}

        gd.on('plotly_click', function(data) {{
            var pt = data.points[0];
            var curve = String(pt.curveNumber);
            var idx   = String(pt.pointIndex);
            var g = groupTraceMap[curve];
            if (!g) return;
            var pos   = groupPos[g];
            var conns = groupConns[g];
            var info  = (groupInfo[g] && groupInfo[g][idx]) ? groupInfo[g][idx] : {{}};
            showPanel(info);
            var p = pos[idx];
            if (p) Plotly.restyle(gd, {{x: [[p[0]]], y: [[p[1]]]}}, [hlTraceIdx]);
            if (conns && conns[idx]) {{
                var lx = [], ly = [];
                conns[idx].forEach(function(seg) {{
                    lx.push(seg[0], seg[2], null);
                    ly.push(seg[1], seg[3], null);
                }});
                Plotly.restyle(gd, {{x: [lx], y: [ly]}}, [lineTraceIdx]);
            }} else {{
                Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [lineTraceIdx]);
            }}
            btn.style.display = 'block';
        }});

        btn.addEventListener('click', reset);
        document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') reset(); }});

        // Prevent axis zoom-to-fit when toggling legend items
        gd.on('plotly_legendclick', function() {{
            var xr = gd._fullLayout.xaxis.range.slice();
            var yr = gd._fullLayout.yaxis.range.slice();
            setTimeout(function() {{
                Plotly.relayout(gd, {{'xaxis.range': xr, 'yaxis.range': yr}});
            }}, 50);
        }});
        gd.on('plotly_legenddoubleclick', function() {{
            var xr = gd._fullLayout.xaxis.range.slice();
            var yr = gd._fullLayout.yaxis.range.slice();
            setTimeout(function() {{
                Plotly.relayout(gd, {{'xaxis.range': xr, 'yaxis.range': yr}});
            }}, 50);
        }});
    }})();
    </script>
    """

    html_str = html_str.replace('</body>', custom_js + '</body>')
    with open(output_html, 'w') as f:
        f.write(html_str)
    labeled = sum(1 for g in node_groups if g != UNKNOWN_GROUP)
    print(f"Saved to {output_html}")
    print(f"  {len(all_groups)} groups: {', '.join(all_groups)}")
    print(f"  {labeled}/{len(node_groups)} cells labeled ({labeled/len(node_groups)*100:.1f}%)")


def generate_cluster_module_visualization(cp, design_name, module_csv, output_html="cluster_module_visualization.html"):
    """Interactive HTML: cells colored by true Verilog module, filterable by cluster or ICN.

    Args:
        cp: ClusterParser with loaded positions, nets, and clustering labels.
        design_name: Name of the design (used in the title).
        module_csv: Path to cell_id_map.csv (columns: short_id, hier_name, module, group).
        output_html: Path to write the HTML file.
    """
    import csv as _csv

    i = cp.num_snapshots - 1
    col_x = i * 2
    col_y = i * 2 + 1

    # --- Load module CSV ---
    cell_to_group = {}
    cell_to_module = {}
    cell_to_conf = {}
    with open(module_csv, newline='') as f:
        reader = _csv.DictReader(f)
        for row in reader:
            key = row['short_id']
            cell_to_group[key] = row['group']
            cell_to_module[key] = row['module']
            cell_to_conf[key] = row.get('hier_name', '')

    UNKNOWN_GROUP = 'unknown'
    node_groups = []
    for node_id in range(len(cp.node_names)):
        name = cp.node_names[node_id] if node_id < len(cp.node_names) else ''
        node_groups.append(cell_to_group.get(name, UNKNOWN_GROUP))

    # --- Module color palette ---
    _MODULE_PALETTE = {
        'main_sbox':  'rgb(31,119,180)',
        'kexp_sbox':  'rgb(214,39,40)',
        'key_expand': 'rgb(255,127,14)',
        'top':        'rgb(44,160,44)',
        'rcon':       'rgb(0,200,200)',
        'io_regs':    'rgb(180,180,180)',
        'unknown':    'rgb(150,150,150)',
    }
    all_groups = sorted(set(node_groups))

    def _group_color(idx, total):
        h = idx / max(total, 1)
        r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.88)
        return f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"

    group_to_color = {}
    for j, g in enumerate(all_groups):
        group_to_color[g] = _MODULE_PALETTE.get(g, _group_color(j, len(all_groups)))

    # --- Per-node connections (clique model) ---
    node_connections = defaultdict(set)
    for net in cp.net_nodes:
        ids_in_net = [nid for nid, _, _, _ in net if nid < len(cp.labels)]
        for a in ids_in_net:
            for b in ids_in_net:
                if a != b:
                    node_connections[a].add(b)

    has_cell_refs = hasattr(cp, 'node_cell_refs') and len(cp.node_cell_refs) == len(cp.node_names)

    # --- Per-cluster data for Plotly + JS ---
    cluster_labels = sorted([l for l in cp.unique_labels if l != -1])
    all_trace_labels = cluster_labels + [-1]   # -1 = ICN, last trace

    trace_conn_js = {}
    trace_pos_js = {}
    trace_info_js = {}

    fig = go.Figure()

    for trace_idx, label in enumerate(all_trace_labels):
        if label == -1:
            mask = cp.labels == -1
            trace_name = f'ICN ({mask.sum()})'
        else:
            mask = cp.labels == label
            trace_name = f'Cluster {label} ({mask.sum()})'

        node_ids = list(np.where(mask)[0])
        colors = [group_to_color[node_groups[nid]] for nid in node_ids]
        names  = [cp.node_names[nid] if nid < len(cp.node_names) else str(nid) for nid in node_ids]

        fig.add_trace(go.Scattergl(
            x=cp.data[mask, col_x],
            y=cp.data[mask, col_y],
            mode='markers',
            marker=dict(size=3 if label == -1 else 2, color=colors, opacity=0.9),
            name=trace_name,
            hovertemplate='<b>%{customdata[0]}</b><br>module: %{customdata[1]}<br>x=%{x:.0f}, y=%{y:.0f}<extra>' + trace_name + '</extra>',
            customdata=[[names[k], cell_to_module.get(names[k], '—')] for k in range(len(node_ids))],
            visible=True,
            showlegend=False,
        ))

        # JS data for click handler
        conns, positions, infos = {}, {}, {}
        for scatter_idx, nid in enumerate(node_ids):
            positions[str(scatter_idx)] = [float(cp.data[nid, col_x]), float(cp.data[nid, col_y])]
            name = cp.node_names[nid] if nid < len(cp.node_names) else str(nid)
            infos[str(scatter_idx)] = {
                'name': name,
                'group': node_groups[nid],
                'module': cell_to_module.get(name, '—'),
                'conf': cell_to_conf.get(name, '—'),
                'cluster': int(label),
                'ref': (cp.node_cell_refs[nid] if has_cell_refs and nid < len(cp.node_cell_refs) else ''),
            }
            if nid in node_connections:
                ix, iy = float(cp.data[nid, col_x]), float(cp.data[nid, col_y])
                conns[str(scatter_idx)] = [
                    [ix, iy, float(cp.data[t, col_x]), float(cp.data[t, col_y])]
                    for t in node_connections[nid]
                ]
        trace_conn_js[str(trace_idx)] = conns
        trace_pos_js[str(trace_idx)]  = positions
        trace_info_js[str(trace_idx)] = infos

    n_cluster_traces = len(all_trace_labels)
    line_trace_idx = n_cluster_traces
    hl_trace_idx   = n_cluster_traces + 1

    fig.add_trace(go.Scattergl(
        x=[], y=[], mode='lines',
        line=dict(color='rgba(255,50,50,0.7)', width=1.5),
        hoverinfo='skip', name='Connections', showlegend=False,
    ))
    fig.add_trace(go.Scattergl(
        x=[], y=[], mode='markers',
        marker=dict(size=12, color='red', symbol='circle'),
        hoverinfo='skip', name='Selected', showlegend=False,
    ))

    fig.update_layout(
        title=f'{design_name} — Module colors, cluster filter | Click cell for connections',
        xaxis=dict(title='X', scaleanchor='y', scaleratio=1),
        yaxis=dict(title='Y'),
        width=1200, height=1000,
        template='plotly_white',
        uirevision='static',
    )

    config = {'modeBarButtonsToRemove': ['autoScale2d'], 'displaylogo': False}
    html_str = fig.to_html(include_plotlyjs=True, full_html=True, config=config)

    # Build JS cluster label list for button bar
    cluster_labels_js = [int(l) for l in cluster_labels]
    module_legend_html = ''.join(
        f'<span style="display:inline-flex;align-items:center;margin:3px 8px 3px 0;">'
        f'<span style="width:12px;height:12px;border-radius:50%;background:{group_to_color[g]};display:inline-block;margin-right:5px;"></span>'
        f'{g}</span>'
        for g in sorted(group_to_color)
    )

    custom_js = f"""
    <script>
    (function() {{
        var traceConns  = {json.dumps(trace_conn_js)};
        var tracePos    = {json.dumps(trace_pos_js)};
        var traceInfo   = {json.dumps(trace_info_js)};
        var nClusterTraces = {n_cluster_traces};
        var lineTraceIdx   = {line_trace_idx};
        var hlTraceIdx     = {hl_trace_idx};
        var clusterLabels  = {json.dumps(cluster_labels_js)};   // excludes -1
        var icnTraceIdx    = {n_cluster_traces - 1};             // ICN is last cluster trace

        var gd = document.querySelectorAll('.plotly-graph-div')[0];
        var activeTrace = null;   // null = show all

        // ---- Module color legend (top-left) ----
        var legend = document.createElement('div');
        legend.style.cssText = [
            'position:fixed;top:60px;left:16px;z-index:9999;',
            'background:rgba(255,255,255,0.95);border:1px solid #ccc;border-radius:6px;',
            'padding:8px 12px;font-family:sans-serif;font-size:12px;',
            'box-shadow:0 2px 6px rgba(0,0,0,0.12);max-width:220px;line-height:1.8;'
        ].join('');
        legend.innerHTML = '<b style="font-size:13px;">Module</b><br>{module_legend_html}';
        document.body.appendChild(legend);

        // ---- Cluster filter bar (top-centre) ----
        var bar = document.createElement('div');
        bar.style.cssText = [
            'position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;',
            'background:rgba(255,255,255,0.97);border:1px solid #aaa;border-radius:6px;',
            'padding:6px 10px;font-family:sans-serif;font-size:12px;',
            'box-shadow:0 2px 8px rgba(0,0,0,0.14);display:flex;flex-wrap:wrap;gap:4px;',
            'max-width:900px;justify-content:center;'
        ].join('');
        document.body.appendChild(bar);

        function makeBtn(label, traceIdx) {{
            var b = document.createElement('button');
            b.innerText = label;
            b.dataset.traceIdx = String(traceIdx);
            b.style.cssText = [
                'padding:3px 8px;font-size:11px;cursor:pointer;border-radius:3px;',
                'border:1px solid #aaa;background:#f5f5f5;color:#333;'
            ].join('');
            b.addEventListener('click', function() {{
                var xr = gd._fullLayout.xaxis.range.slice();
                var yr = gd._fullLayout.yaxis.range.slice();
                var ti = parseInt(this.dataset.traceIdx);
                if (activeTrace === ti) {{
                    // deselect — show all
                    activeTrace = null;
                    showAll();
                    markActive(null);
                }} else {{
                    activeTrace = ti;
                    showOnly(ti);
                    markActive(ti);
                }}
                setTimeout(function() {{
                    Plotly.relayout(gd, {{'xaxis.range': xr, 'yaxis.range': yr}});
                }}, 50);
                reset();
            }});
            return b;
        }}

        // "All" button
        var allBtn = document.createElement('button');
        allBtn.innerText = 'All';
        allBtn.style.cssText = [
            'padding:3px 10px;font-size:11px;cursor:pointer;border-radius:3px;',
            'border:1px solid #555;background:#333;color:#fff;font-weight:bold;'
        ].join('');
        allBtn.addEventListener('click', function() {{
            var xr = gd._fullLayout.xaxis.range.slice();
            var yr = gd._fullLayout.yaxis.range.slice();
            activeTrace = null;
            showAll();
            markActive(null);
            setTimeout(function() {{
                Plotly.relayout(gd, {{'xaxis.range': xr, 'yaxis.range': yr}});
            }}, 50);
            reset();
        }});
        bar.appendChild(allBtn);

        clusterLabels.forEach(function(lbl, j) {{
            bar.appendChild(makeBtn('C' + lbl, j));
        }});
        bar.appendChild(makeBtn('ICN', icnTraceIdx));

        function markActive(ti) {{
            bar.querySelectorAll('button').forEach(function(b, idx) {{
                if (idx === 0) {{
                    b.style.background = (ti === null) ? '#333' : '#f5f5f5';
                    b.style.color      = (ti === null) ? '#fff' : '#333';
                }} else {{
                    var bti = parseInt(b.dataset.traceIdx);
                    b.style.background = (bti === ti) ? '#1a6fc4' : '#f5f5f5';
                    b.style.color      = (bti === ti) ? '#fff'    : '#333';
                }}
            }});
        }}

        function showAll() {{
            var vis = [];
            for (var k = 0; k < nClusterTraces; k++) vis.push(true);
            vis.push(false); vis.push(false);  // line + hl traces stay hidden
            Plotly.restyle(gd, {{visible: vis}});
        }}

        function showOnly(ti) {{
            var vis = [];
            for (var k = 0; k < nClusterTraces; k++) vis.push(k === ti);
            vis.push(false); vis.push(false);
            Plotly.restyle(gd, {{visible: vis}});
        }}

        // ---- Info panel + connection lines ----
        var panel = document.createElement('div');
        panel.style.cssText = [
            'position:fixed;bottom:20px;right:20px;z-index:9999;',
            'background:rgba(255,255,255,0.96);border:1px solid #ccc;border-radius:6px;',
            'padding:12px 16px;font-family:monospace;font-size:13px;',
            'min-width:220px;max-width:360px;',
            'box-shadow:0 2px 8px rgba(0,0,0,0.18);display:none;line-height:1.6;'
        ].join('');
        document.body.appendChild(panel);

        var resetBtn = document.createElement('button');
        resetBtn.innerText = 'Clear';
        resetBtn.style.cssText = 'position:fixed;top:10px;right:20px;z-index:9999;padding:6px 14px;font-size:13px;cursor:pointer;background:#e74c3c;color:white;border:none;border-radius:4px;display:none;';
        document.body.appendChild(resetBtn);

        function reset() {{
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [lineTraceIdx]);
            Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [hlTraceIdx]);
            resetBtn.style.display = 'none';
            panel.style.display = 'none';
        }}

        gd.on('plotly_click', function(data) {{
            var pt    = data.points[0];
            var curve = String(pt.curveNumber);
            var idx   = String(pt.pointIndex);
            if (parseInt(curve) >= nClusterTraces) return;

            var info  = (traceInfo[curve] && traceInfo[curve][idx]) ? traceInfo[curve][idx] : {{}};
            var pos   = tracePos[curve];
            var conns = traceConns[curve];

            var clLabel = info.cluster === -1 ? '<i>ICN</i>' : String(info.cluster);
            var h = '<b style="font-size:14px;">' + (info.name || '—') + '</b><br>';
            h += '<span style="color:#555;">Group:</span> <b>' + (info.group || '—') + '</b><br>';
            h += '<span style="color:#555;">Module:</span> ' + (info.module || '—') + '<br>';
            if (info.conf) h += '<span style="color:#555;">Hier name:</span> ' + info.conf + '<br>';
            h += '<span style="color:#555;">Cluster:</span> ' + clLabel + '<br>';
            if (info.ref) h += '<span style="color:#555;">Cell ref:</span> ' + info.ref + '<br>';
            panel.innerHTML = h;
            panel.style.display = 'block';

            var p = pos && pos[idx];
            if (p) Plotly.restyle(gd, {{x: [[p[0]]], y: [[p[1]]]}}, [hlTraceIdx]);

            if (conns && conns[idx]) {{
                var lx = [], ly = [];
                conns[idx].forEach(function(seg) {{
                    lx.push(seg[0], seg[2], null);
                    ly.push(seg[1], seg[3], null);
                }});
                Plotly.restyle(gd, {{x: [lx], y: [ly]}}, [lineTraceIdx]);
            }} else {{
                Plotly.restyle(gd, {{x: [[]], y: [[]]}}, [lineTraceIdx]);
            }}
            resetBtn.style.display = 'block';
        }});

        resetBtn.addEventListener('click', reset);
        document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') reset(); }});
    }})();
    </script>
    """

    html_str = html_str.replace('</body>', custom_js + '</body>')
    with open(output_html, 'w') as f:
        f.write(html_str)
    print(f"Saved to {output_html}")
    print(f"  {len(cluster_labels)} clusters + ICN | {len(all_groups)} module groups")
