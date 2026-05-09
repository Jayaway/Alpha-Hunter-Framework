# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 独立关系图谱可视化
================================================
实现类似 Obsidian 的交互式关系图谱界面，无需依赖 Obsidian。

功能：
  1. 力导向图布局
  2. 节点拖拽
  3. 缩放平移
  4. 节点搜索过滤
  5. 点击查看详情
  6. 关系高亮

启动方式：
  python3 graph_viewer.py
  然后访问 http://localhost:8080
"""

import os
import json
import http.server
import socketserver
import webbrowser
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>情报关系图谱</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #1a1a2e;
            color: #eee;
            overflow: hidden;
        }

        #container {
            display: flex;
            height: 100vh;
        }

        #sidebar {
            width: 320px;
            background: #16213e;
            border-right: 1px solid #0f3460;
            display: flex;
            flex-direction: column;
            z-index: 100;
        }

        #sidebar-header {
            padding: 20px;
            border-bottom: 1px solid #0f3460;
        }

        #sidebar-header h1 {
            font-size: 18px;
            margin-bottom: 10px;
            color: #e94560;
        }

        #search-box {
            width: 100%;
            padding: 10px 15px;
            border: 1px solid #0f3460;
            border-radius: 8px;
            background: #1a1a2e;
            color: #eee;
            font-size: 14px;
        }

        #search-box:focus {
            outline: none;
            border-color: #e94560;
        }

        #stats {
            padding: 15px 20px;
            background: #0f3460;
            font-size: 12px;
            color: #aaa;
        }

        #stats span {
            margin-right: 15px;
        }

        #stats strong {
            color: #e94560;
        }

        #filter-section {
            padding: 15px 20px;
            border-bottom: 1px solid #0f3460;
        }

        .filter-title {
            font-size: 12px;
            color: #888;
            margin-bottom: 10px;
        }

        .filter-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .filter-tag {
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }

        .filter-tag.active {
            border-color: currentColor;
        }

        .filter-tag[data-type="account"] { background: #4a5568; color: #63b3ed; }
        .filter-tag[data-type="organization"] { background: #4a5568; color: #f6ad55; }
        .filter-tag[data-type="location"] { background: #4a5568; color: #68d391; }
        .filter-tag[data-type="asset"] { background: #4a5568; color: #fc8181; }
        .filter-tag[data-type="event"] { background: #4a5568; color: #b794f4; }
        .filter-tag[data-type="hashtag"] { background: #4a5568; color: #4fd1c5; }
        .filter-tag[data-type="keyword"] { background: #4a5568; color: #faf089; }

        #entity-list {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }

        .entity-item {
            padding: 12px 15px;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.2s;
            margin-bottom: 5px;
        }

        .entity-item:hover {
            background: #0f3460;
        }

        .entity-item.selected {
            background: #e94560;
        }

        .entity-name {
            font-weight: 500;
            margin-bottom: 4px;
        }

        .entity-meta {
            font-size: 11px;
            color: #888;
        }

        .entity-type-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            margin-right: 8px;
        }

        #graph-container {
            flex: 1;
            position: relative;
            background: radial-gradient(circle at center, #1a1a2e 0%, #0f0f1a 100%);
        }

        #graph-canvas {
            width: 100%;
            height: 100%;
        }

        #controls {
            position: absolute;
            bottom: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }

        .control-btn {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 1px solid #0f3460;
            background: #16213e;
            color: #eee;
            font-size: 18px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .control-btn:hover {
            background: #e94560;
            border-color: #e94560;
        }

        #detail-panel {
            position: absolute;
            top: 20px;
            right: 20px;
            width: 350px;
            background: #16213e;
            border-radius: 12px;
            border: 1px solid #0f3460;
            display: none;
            max-height: 80vh;
            overflow-y: auto;
        }

        #detail-panel.visible {
            display: block;
        }

        #detail-header {
            padding: 20px;
            border-bottom: 1px solid #0f3460;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        #detail-header h2 {
            font-size: 16px;
        }

        #close-detail {
            background: none;
            border: none;
            color: #888;
            font-size: 20px;
            cursor: pointer;
        }

        #close-detail:hover {
            color: #e94560;
        }

        #detail-content {
            padding: 20px;
        }

        .detail-section {
            margin-bottom: 20px;
        }

        .detail-section h3 {
            font-size: 12px;
            color: #888;
            margin-bottom: 10px;
            text-transform: uppercase;
        }

        .detail-stat {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #0f3460;
        }

        .related-entity {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: #1a1a2e;
            border-radius: 6px;
            margin-bottom: 6px;
            cursor: pointer;
        }

        .related-entity:hover {
            background: #0f3460;
        }

        .relation-type {
            font-size: 11px;
            color: #888;
        }

        .mention-item {
            padding: 10px;
            background: #1a1a2e;
            border-radius: 6px;
            margin-bottom: 8px;
            font-size: 13px;
        }

        .mention-time {
            font-size: 11px;
            color: #888;
            margin-top: 5px;
        }

        #tooltip {
            position: absolute;
            padding: 8px 12px;
            background: #16213e;
            border: 1px solid #0f3460;
            border-radius: 6px;
            font-size: 12px;
            pointer-events: none;
            display: none;
            z-index: 1000;
        }

        #loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
        }

        .spinner {
            width: 50px;
            height: 50px;
            border: 3px solid #0f3460;
            border-top-color: #e94560;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        #minimap {
            position: absolute;
            bottom: 20px;
            left: 20px;
            width: 150px;
            height: 100px;
            background: #16213e;
            border: 1px solid #0f3460;
            border-radius: 8px;
            overflow: hidden;
        }

        #minimap-canvas {
            width: 100%;
            height: 100%;
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="sidebar">
            <div id="sidebar-header">
                <h1>📊 情报关系图谱</h1>
                <input type="text" id="search-box" placeholder="搜索实体...">
            </div>
            <div id="stats">
                <span>节点: <strong id="node-count">0</strong></span>
                <span>关系: <strong id="edge-count">0</strong></span>
                <span>更新: <strong id="update-time">-</strong></span>
            </div>
            <div id="filter-section">
                <div class="filter-title">实体类型筛选</div>
                <div class="filter-tags">
                    <span class="filter-tag active" data-type="account">🐦 账号</span>
                    <span class="filter-tag active" data-type="organization">🏛️ 组织</span>
                    <span class="filter-tag active" data-type="location">📍 地点</span>
                    <span class="filter-tag active" data-type="asset">💰 资产</span>
                    <span class="filter-tag active" data-type="event">⚡ 事件</span>
                    <span class="filter-tag active" data-type="hashtag">🏷️ 话题</span>
                    <span class="filter-tag active" data-type="keyword">🔑 关键词</span>
                </div>
            </div>
            <div id="entity-list"></div>
        </div>

        <div id="graph-container">
            <canvas id="graph-canvas"></canvas>
            
            <div id="loading">
                <div class="spinner"></div>
                <div>加载图谱数据...</div>
            </div>

            <div id="controls">
                <button class="control-btn" id="zoom-in" title="放大">+</button>
                <button class="control-btn" id="zoom-out" title="缩小">−</button>
                <button class="control-btn" id="reset-view" title="重置视图">⌂</button>
                <button class="control-btn" id="fullscreen" title="全屏">⛶</button>
            </div>

            <div id="detail-panel">
                <div id="detail-header">
                    <h2 id="detail-title">实体名称</h2>
                    <button id="close-detail">×</button>
                </div>
                <div id="detail-content"></div>
            </div>

            <div id="minimap">
                <canvas id="minimap-canvas"></canvas>
            </div>
        </div>
    </div>

    <div id="tooltip"></div>

    <script>
        // 图谱数据
        let graphData = { nodes: [], edges: [] };
        let filteredNodes = [];
        let filteredEdges = [];
        
        // 画布状态
        let canvas, ctx;
        let minimapCanvas, minimapCtx;
        let width, height;
        let transform = { x: 0, y: 0, scale: 1 };
        let isDragging = false;
        let dragNode = null;
        let dragStart = { x: 0, y: 0 };
        let hoveredNode = null;
        let selectedNode = null;
        let nodeMap = new Map();
        let animationTick = 0;
        
        // 实体类型颜色
        const typeColors = {
            account: '#63b3ed',
            organization: '#f6ad55',
            location: '#68d391',
            asset: '#fc8181',
            event: '#b794f4',
            hashtag: '#4fd1c5',
            keyword: '#faf089',
            person: '#ed8936'
        };
        
        const typeLabels = {
            account: '账号',
            organization: '组织机构',
            location: '地点',
            asset: '资产',
            event: '事件',
            hashtag: '话题',
            keyword: '关键词',
            person: '人物'
        };

        const relationLabels = {
            mentions: '提及',
            discusses: '讨论',
            reports: '报道',
            posts_about: '发布',
            co_occurs: '共现'
        };
        
        // 初始化
        function init() {
            canvas = document.getElementById('graph-canvas');
            ctx = canvas.getContext('2d');
            minimapCanvas = document.getElementById('minimap-canvas');
            minimapCtx = minimapCanvas.getContext('2d');
            
            resizeCanvas();
            window.addEventListener('resize', resizeCanvas);
            
            setupEventListeners();
            loadGraphData();
        }
        
        function resizeCanvas() {
            const container = document.getElementById('graph-container');
            width = container.clientWidth;
            height = container.clientHeight;
            
            canvas.width = width * window.devicePixelRatio;
            canvas.height = height * window.devicePixelRatio;
            canvas.style.width = width + 'px';
            canvas.style.height = height + 'px';
            ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
            
            minimapCanvas.width = 150;
            minimapCanvas.height = 100;
        }
        
        function setupEventListeners() {
            // 搜索
            document.getElementById('search-box').addEventListener('input', onSearch);
            
            // 类型筛选
            document.querySelectorAll('.filter-tag').forEach(tag => {
                tag.addEventListener('click', toggleFilter);
            });
            
            // 画布交互
            canvas.addEventListener('mousedown', onMouseDown);
            canvas.addEventListener('mousemove', onMouseMove);
            canvas.addEventListener('mouseup', onMouseUp);
            canvas.addEventListener('wheel', onWheel);
            canvas.addEventListener('dblclick', onDoubleClick);
            
            // 控制按钮
            document.getElementById('zoom-in').addEventListener('click', () => zoom(1.2));
            document.getElementById('zoom-out').addEventListener('click', () => zoom(0.8));
            document.getElementById('reset-view').addEventListener('click', resetView);
            document.getElementById('fullscreen').addEventListener('click', toggleFullscreen);
            document.getElementById('close-detail').addEventListener('click', closeDetail);
        }
        
        function loadGraphData() {
            fetch('/api/graph')
                .then(res => res.json())
                .then(data => {
                    graphData = data;
                    initializeNodes();
                    applyFilters();
                    document.getElementById('loading').style.display = 'none';
                    render();
                })
                .catch(err => {
                    console.error('加载失败:', err);
                    document.getElementById('loading').innerHTML = '<div style="color:#e94560">加载失败，请检查数据</div>';
                });
        }
        
        function initializeNodes() {
            const centerX = width / 2;
            const centerY = height / 2;
            const maxMention = Math.max(...graphData.nodes.map(n => n.mention_count || 1), 1);
            
            graphData.nodes.forEach((node, i) => {
                const angle = (2 * Math.PI * i) / graphData.nodes.length;
                const radius = 200 + Math.random() * 150;
                node.x = centerX + radius * Math.cos(angle);
                node.y = centerY + radius * Math.sin(angle);
                node.vx = 0;
                node.vy = 0;
                node.fontSize = getNodeFontSize(node, maxMention);
                node.radius = getNodeRadius(node);
                node.pulse = Math.random() * Math.PI * 2;
            });
            nodeMap = new Map(graphData.nodes.map(node => [node.id, node]));
            
            updateStats();
        }
        
        function getNodeRadius(node) {
            const textWidth = String(node.label || node.id).length * (node.fontSize || 14) * 0.95;
            return Math.max(16, Math.min(80, textWidth / 2 + 10));
        }

        function getNodeFontSize(node, maxMention) {
            const count = node.mention_count || 1;
            const ratio = Math.sqrt(count / maxMention);
            return Math.round(13 + ratio * 39);
        }

        function getEdgeWidth(edge, highlighted = false) {
            const weight = edge.weight || 1;
            const width = 0.7 + Math.log2(weight + 1) * 0.75;
            return highlighted ? Math.max(2.5, width + 1.5) : Math.min(width, 5);
        }
        
        function applyFilters() {
            const searchTerm = document.getElementById('search-box').value.toLowerCase();
            const activeTypes = Array.from(document.querySelectorAll('.filter-tag.active'))
                .map(t => t.dataset.type);
            
            filteredNodes = graphData.nodes.filter(node => {
                const typeMatch = activeTypes.includes(node.type);
                const searchText = `${node.id || ''} ${node.label || ''} ${node.detail || ''}`.toLowerCase();
                const searchMatch = !searchTerm || searchText.includes(searchTerm);
                return typeMatch && searchMatch;
            });
            
            const nodeIds = new Set(filteredNodes.map(n => n.id));
            filteredEdges = graphData.edges
                .filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target))
                .sort((a, b) => (a.weight || 0) - (b.weight || 0));
            
            updateEntityList();
        }
        
        function updateStats() {
            document.getElementById('node-count').textContent = graphData.nodes.length;
            document.getElementById('edge-count').textContent = graphData.edges.length;
            document.getElementById('update-time').textContent = 
                new Date().toLocaleTimeString();
        }
        
        function updateEntityList() {
            const list = document.getElementById('entity-list');
            const sorted = [...filteredNodes].sort((a, b) => 
                (b.mention_count || 0) - (a.mention_count || 0)
            );
            
            list.innerHTML = sorted.slice(0, 50).map(node => `
                <div class="entity-item" data-id="${node.id}">
                    <div class="entity-name">
                        <span class="entity-type-badge" style="background:${typeColors[node.type]}22;color:${typeColors[node.type]}">
                            ${node.type_label || typeLabels[node.type] || node.type}
                        </span>
                        ${node.label || node.id}
                    </div>
                    <div class="entity-meta">
                        ${node.detail || node.id} · 提及 ${node.mention_count || 0} 次
                    </div>
                </div>
            `).join('');
            
            list.querySelectorAll('.entity-item').forEach(item => {
                item.addEventListener('click', () => {
                    const node = filteredNodes.find(n => n.id === item.dataset.id);
                    if (node) selectNode(node);
                });
            });
        }
        
        // 力导向模拟
        function simulate() {
            const alpha = 0.24;
            const repulsion = 8500;
            const attraction = 0.012;
            const centerForce = 0.008;
            
            filteredNodes.forEach(node => {
                // 排斥力
                filteredNodes.forEach(other => {
                    if (node === other) return;
                    const dx = node.x - other.x;
                    const dy = node.y - other.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const minDist = node.radius + other.radius + 24;
                    const force = (repulsion + minDist * 40) / (dist * dist);
                    node.vx += (dx / dist) * force * alpha;
                    node.vy += (dy / dist) * force * alpha;
                });
                
                // 中心引力
                node.vx += (width / 2 - node.x) * centerForce * alpha;
                node.vy += (height / 2 - node.y) * centerForce * alpha;
            });
            
            // 弹簧力
            filteredEdges.forEach(edge => {
                const source = nodeMap.get(edge.source);
                const target = nodeMap.get(edge.target);
                if (!source || !target) return;
                
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const desired = 90 + source.radius + target.radius + Math.max(0, 6 - (edge.weight || 1)) * 8;
                const force = (dist - desired) * attraction * Math.min(edge.weight || 1, 8);
                
                source.vx += (dx / dist) * force * alpha;
                source.vy += (dy / dist) * force * alpha;
                target.vx -= (dx / dist) * force * alpha;
                target.vy -= (dy / dist) * force * alpha;
            });
            
            // 应用速度
            filteredNodes.forEach(node => {
                if (node === dragNode) return;
                node.x += node.vx;
                node.y += node.vy;
                node.vx *= 0.88;
                node.vy *= 0.88;
                
                // 边界约束
                node.x = Math.max(50, Math.min(width - 50, node.x));
                node.y = Math.max(50, Math.min(height - 50, node.y));
            });
        }
        
        // 渲染
        function render() {
            animationTick += 1;
            ctx.clearRect(0, 0, width, height);
            
            ctx.save();
            ctx.translate(transform.x, transform.y);
            ctx.scale(transform.scale, transform.scale);
            
            // 绘制边
            filteredEdges.forEach(edge => {
                const source = nodeMap.get(edge.source);
                const target = nodeMap.get(edge.target);
                if (!source || !target) return;
                
                const isHighlighted = selectedNode && 
                    (edge.source === selectedNode.id || edge.target === selectedNode.id);
                
                ctx.beginPath();
                ctx.moveTo(source.x, source.y);
                ctx.lineTo(target.x, target.y);
                ctx.strokeStyle = isHighlighted ? 
                    'rgba(233, 69, 96, 0.85)' : 'rgba(130, 140, 170, 0.25)';
                ctx.lineWidth = getEdgeWidth(edge, isHighlighted);
                ctx.stroke();

                if (isHighlighted || (edge.weight || 0) >= 8) {
                    drawEdgeParticle(source, target, edge);
                }
            });
            
            // 绘制节点
            filteredNodes.forEach(node => {
                const isSelected = selectedNode && node.id === selectedNode.id;
                const isHovered = hoveredNode && node.id === hoveredNode.id;
                const isConnected = selectedNode && filteredEdges.some(e => 
                    (e.source === selectedNode.id && e.target === node.id) ||
                    (e.target === selectedNode.id && e.source === node.id)
                );
                
                const color = typeColors[node.type] || '#888';
                const radius = node.radius;
                const pulse = 1 + Math.sin(animationTick * 0.035 + node.pulse) * 0.04;
                
                // 光晕效果
                ctx.beginPath();
                ctx.arc(node.x, node.y, (radius + (isSelected || isHovered ? 14 : 6)) * pulse, 0, Math.PI * 2);
                ctx.fillStyle = isSelected || isHovered ? color + '33' : color + '12';
                ctx.fill();
                
                // 节点底色
                ctx.beginPath();
                ctx.arc(node.x, node.y, Math.max(8, radius * 0.42), 0, Math.PI * 2);
                ctx.fillStyle = isSelected ? '#e94560' : 
                    (isConnected ? color + 'cc' : color + '66');
                ctx.fill();
                
                // 边框
                if (isSelected || isHovered) {
                    ctx.strokeStyle = '#fff';
                    ctx.lineWidth = 2.5;
                    ctx.stroke();
                }
                
                // 关键词文本是主体，出现比例越高字体越大
                ctx.font = `${isSelected ? '700' : '600'} ${node.fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.lineWidth = Math.max(3, node.fontSize * 0.16);
                ctx.strokeStyle = 'rgba(10, 12, 24, 0.88)';
                const label = node.label || node.id;
                ctx.strokeText(label, node.x, node.y);
                ctx.fillStyle = isSelected ? '#fff' : (isConnected ? '#fff' : color);
                ctx.fillText(label, node.x, node.y);
            });
            
            ctx.restore();
            
            // 绘制小地图
            renderMinimap();
        }

        function drawEdgeParticle(source, target, edge) {
            const progress = ((animationTick * 0.008 * Math.max(1, Math.min(edge.weight || 1, 6))) % 1);
            const x = source.x + (target.x - source.x) * progress;
            const y = source.y + (target.y - source.y) * progress;
            ctx.beginPath();
            ctx.arc(x, y, Math.min(4, 1.6 + (edge.weight || 1) * 0.12), 0, Math.PI * 2);
            ctx.fillStyle = selectedNode ? 'rgba(255,255,255,0.9)' : 'rgba(233,69,96,0.75)';
            ctx.fill();
        }
        
        function renderMinimap() {
            minimapCtx.fillStyle = '#16213e';
            minimapCtx.fillRect(0, 0, 150, 100);
            
            const scale = 0.08;
            minimapCtx.save();
            minimapCtx.translate(75, 50);
            minimapCtx.scale(scale, scale);
            
            filteredNodes.forEach(node => {
                minimapCtx.beginPath();
                minimapCtx.arc(node.x - width/2, node.y - height/2, Math.max(2, node.fontSize / 12), 0, Math.PI * 2);
                minimapCtx.fillStyle = typeColors[node.type] || '#888';
                minimapCtx.fill();
            });
            
            minimapCtx.restore();
        }
        
        // 交互处理
        function onMouseDown(e) {
            const pos = getMousePos(e);
            dragStart = pos;
            
            const node = getNodeAtPos(pos);
            if (node) {
                dragNode = node;
                selectNode(node);
            } else {
                isDragging = true;
            }
        }
        
        function onMouseMove(e) {
            const pos = getMousePos(e);
            
            if (dragNode) {
                dragNode.x = pos.x / transform.scale - transform.x / transform.scale;
                dragNode.y = pos.y / transform.scale - transform.y / transform.scale;
            } else if (isDragging) {
                transform.x += pos.x - dragStart.x;
                transform.y += pos.y - dragStart.y;
                dragStart = pos;
            } else {
                const node = getNodeAtPos(pos);
                if (node !== hoveredNode) {
                    hoveredNode = node;
                    showTooltip(e, node);
                }
            }
        }
        
        function onMouseUp() {
            isDragging = false;
            dragNode = null;
        }
        
        function onWheel(e) {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            zoom(delta, getMousePos(e));
        }
        
        function onDoubleClick(e) {
            const node = getNodeAtPos(getMousePos(e));
            if (node) {
                focusNode(node);
            }
        }
        
        function getMousePos(e) {
            const rect = canvas.getBoundingClientRect();
            return {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top
            };
        }
        
        function getNodeAtPos(pos) {
            const x = pos.x / transform.scale - transform.x / transform.scale;
            const y = pos.y / transform.scale - transform.y / transform.scale;
            
            return filteredNodes.find(node => {
                const dx = node.x - x;
                const dy = node.y - y;
                return Math.sqrt(dx * dx + dy * dy) < node.radius;
            });
        }
        
        function zoom(factor, center = null) {
            const newScale = Math.max(0.2, Math.min(3, transform.scale * factor));
            
            if (center) {
                transform.x = center.x - (center.x - transform.x) * (newScale / transform.scale);
                transform.y = center.y - (center.y - transform.y) * (newScale / transform.scale);
            }
            
            transform.scale = newScale;
        }
        
        function resetView() {
            transform = { x: 0, y: 0, scale: 1 };
        }
        
        function focusNode(node) {
            transform.scale = 1.5;
            transform.x = width / 2 - node.x * transform.scale;
            transform.y = height / 2 - node.y * transform.scale;
        }
        
        function selectNode(node) {
            selectedNode = node;
            showDetail(node);
            
            document.querySelectorAll('.entity-item').forEach(item => {
                item.classList.toggle('selected', item.dataset.id === node.id);
            });
        }
        
        function showDetail(node) {
            const panel = document.getElementById('detail-panel');
            const title = document.getElementById('detail-title');
            const content = document.getElementById('detail-content');
            
            title.textContent = node.label || node.id;
            
            const relatedEdges = filteredEdges.filter(e => 
                e.source === node.id || e.target === node.id
            );
            
            const relatedEntities = relatedEdges.map(e => {
                const otherId = e.source === node.id ? e.target : e.source;
                const other = filteredNodes.find(n => n.id === otherId);
                return {
                    id: otherId,
                    label: other?.label || otherId,
                    type: other?.type,
                    relation: e.type,
                    weight: e.weight
                };
            });
            
            content.innerHTML = `
                <div class="detail-section">
                    <h3>基本信息</h3>
                    <div class="detail-stat">
                        <span>类型</span>
                        <span style="color:${typeColors[node.type]}">${node.type_label || typeLabels[node.type] || node.type}</span>
                    </div>
                    <div class="detail-stat">
                        <span>原始名称</span>
                        <span>${node.detail || node.id}</span>
                    </div>
                    <div class="detail-stat">
                        <span>提及次数</span>
                        <span>${node.mention_count || 0}</span>
                    </div>
                    <div class="detail-stat">
                        <span>总互动量</span>
                        <span>${(node.engagement || 0).toLocaleString()}</span>
                    </div>
                </div>
                
                <div class="detail-section">
                    <h3>关联实体 (${relatedEntities.length})</h3>
                    ${relatedEntities.slice(0, 10).map(e => `
                        <div class="related-entity" data-id="${e.id}">
                            <span>
                                <span style="color:${typeColors[e.type]}">${e.label}</span>
                            </span>
                            <span class="relation-type">${relationLabels[e.relation] || e.relation || '关联'} ×${e.weight || 1}</span>
                        </div>
                    `).join('')}
                </div>
            `;
            
            content.querySelectorAll('.related-entity').forEach(item => {
                item.addEventListener('click', () => {
                    const n = filteredNodes.find(n => n.id === item.dataset.id);
                    if (n) {
                        selectNode(n);
                        focusNode(n);
                    }
                });
            });
            
            panel.classList.add('visible');
        }
        
        function closeDetail() {
            document.getElementById('detail-panel').classList.remove('visible');
            selectedNode = null;
            document.querySelectorAll('.entity-item').forEach(item => {
                item.classList.remove('selected');
            });
        }
        
        function showTooltip(e, node) {
            const tooltip = document.getElementById('tooltip');
            if (node) {
                tooltip.innerHTML = `
                    <strong>${node.label || node.id}</strong><br>
                    <span style="color:${typeColors[node.type]}">${node.type_label || typeLabels[node.type]}</span>
                    <span style="color:#888"> · ${node.detail || node.id}</span><br>
                    <span style="color:#888"> · 提及 ${node.mention_count || 0} 次</span>
                `;
                tooltip.style.left = (e.clientX + 15) + 'px';
                tooltip.style.top = (e.clientY + 15) + 'px';
                tooltip.style.display = 'block';
            } else {
                tooltip.style.display = 'none';
            }
        }
        
        function onSearch(e) {
            applyFilters();
        }
        
        function toggleFilter(e) {
            e.target.classList.toggle('active');
            applyFilters();
        }
        
        function toggleFullscreen() {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                document.documentElement.requestFullscreen();
            }
        }
        
        // 动画循环
        let frameCount = 0;
        function animate() {
            frameCount++;
            if (frameCount % 3 === 0) {
                simulate();
            }
            render();
            requestAnimationFrame(animate);
        }
        
        // 启动
        init();
        animate();
    </script>
</body>
</html>
"""


class GraphHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """图谱 HTTP 请求处理器"""

    def __init__(self, *args, graph_data=None, **kwargs):
        self.graph_data = graph_data or {"nodes": [], "edges": []}
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

        elif self.path == '/api/graph':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(self.graph_data, ensure_ascii=False).encode('utf-8'))

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def create_handler(graph_data):
    """创建带有图谱数据的处理器"""
    def handler(*args, **kwargs):
        return GraphHTTPHandler(*args, graph_data=graph_data, **kwargs)
    return handler


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class GraphViewer:
    """关系图谱查看器"""

    def __init__(self, port: int = 8080):
        self.port = port
        self.graph_data = {"nodes": [], "edges": []}
        self.server = None

    def update_data(self, nodes: List[dict], edges: List[dict]):
        """更新图谱数据"""
        self.graph_data = {
            "nodes": nodes,
            "edges": edges,
            "generated": datetime.now().isoformat()
        }

    def load_from_file(self, filepath: str):
        """从文件加载图谱数据"""
        with open(filepath, 'r', encoding='utf-8') as f:
            self.graph_data = json.load(f)

    def start(self, open_browser: bool = True):
        """启动图谱服务器"""
        handler = create_handler(self.graph_data)

        with ReusableTCPServer(("", self.port), handler) as httpd:
            url = f"http://localhost:{self.port}"
            print(f"\n{'=' * 60}")
            print(f"  情报关系图谱服务已启动")
            print(f"  访问地址: {url}")
            print(f"{'=' * 60}\n")

            if open_browser:
                webbrowser.open(url)

            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n服务已停止")


def run_viewer(port: int = 8080, graph_file: str = "./graph_data/关系图谱.json"):
    """运行图谱查看器"""
    viewer = GraphViewer(port)

    if graph_file and os.path.exists(graph_file):
        viewer.load_from_file(graph_file)

    viewer.start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="情报关系图谱查看器")
    parser.add_argument("--port", type=int, default=8080, help="服务端口")
    parser.add_argument("--file", type=str, default="./graph_data/关系图谱.json", help="图谱数据文件")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")

    args = parser.parse_args()

    viewer = GraphViewer(args.port)

    if args.file and os.path.exists(args.file):
        viewer.load_from_file(args.file)
    else:
        print(f"图谱数据文件不存在: {args.file}")
        print("可先运行: python3 graph_engine.py")

    viewer.start(open_browser=not args.no_browser)
