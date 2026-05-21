<script lang="ts">
/**
 * Pipeline as a Svelte Flow graph. Nodes carry their own settings — no
 * separate "Pipeline (live)" diagram + "Settings" forms duplicating the
 * same knobs. Reactive arrows, drag, and inline controls come from
 * @xyflow/svelte.
 */
import {
  SvelteFlow,
  Background,
  Controls,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/svelte';
import '@xyflow/svelte/dist/style.css';
import PaddleNode from './pipeline/PaddleNode.svelte';
import GlinerNode from './pipeline/GlinerNode.svelte';
import IoNode from './pipeline/IoNode.svelte';
import PipelineInspector from './pipeline/PipelineInspector.svelte';
import { editor } from '$lib/state.svelte';

// SvelteFlow's NodeTypes index signature is a *general* Node<unknown,…>
// component; IoNode narrows its data type. Cast is the documented escape
// hatch — runtime shape matches.
const nodeTypes = { paddle: PaddleNode, gliner: GlinerNode, io: IoNode } as unknown as NodeTypes;

// Static layout — positions are fixed; nodes are compact summaries. Edge
// arrows reflect data flow. Detailed editing lives in PipelineInspector
// (right panel), driven by `selectedId` below.
let nodes = $state<Node[]>([
  {
    id: 'input',
    type: 'io',
    position: { x: 0, y: 80 },
    data: { label: 'Image', sub: 'png · pdf', side: 'in' },
    sourcePosition: Position.Right,
    deletable: false,
    draggable: true,
  },
  {
    id: 'paddle',
    type: 'paddle',
    position: { x: 180, y: 40 },
    data: {},
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    deletable: false,
    draggable: true,
  },
  {
    id: 'gliner',
    type: 'gliner',
    position: { x: 480, y: 20 },
    data: {},
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    deletable: false,
    draggable: true,
  },
  {
    id: 'output',
    type: 'io',
    position: { x: 860, y: 80 },
    data: { label: 'PII spans', sub: 'redaction canvas', side: 'out' },
    targetPosition: Position.Left,
    deletable: false,
    draggable: true,
  },
]);

// Active node id (or null if nothing selected). Svelte Flow flips
// `node.selected` on the bound nodes array — we mirror that into a single id
// for PipelineInspector to switch on.
let selectedId = $derived(
  nodes.find((n) => (n as { selected?: boolean }).selected)?.id ?? null,
);

let edges = $state<Edge[]>([
  {
    id: 'in-paddle',
    source: 'input',
    target: 'paddle',
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
    style: 'stroke: var(--text3);',
  },
  {
    id: 'paddle-gliner',
    source: 'paddle',
    target: 'gliner',
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
    style: 'stroke: var(--text3);',
  },
  {
    id: 'gliner-out',
    source: 'gliner',
    target: 'output',
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
    style: 'stroke: var(--text3);',
  },
]);

// Drive the "dashes flow" animation on each edge from the live pipeline
// stage. Edge i is animated while its source node is producing.
$effect(() => {
  const stage = editor.pipelineStage;
  const animate = (id: string, on: boolean) => {
    const e = edges.find((edge) => edge.id === id);
    if (e && e.animated !== on) e.animated = on;
  };
  animate('in-paddle', stage === 'ocr');
  animate('paddle-gliner', stage === 'gliner');
  animate('gliner-out', stage === 'done');
});
</script>

<div class="flex h-full w-full overflow-hidden bg-background/40">
  <div class="flex-1 min-w-0">
    <SvelteFlow
      bind:nodes
      bind:edges
      {nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      nodesConnectable={false}
      elementsSelectable={true}
      proOptions={{ hideAttribution: true }}
    >
      <Background bgColor="transparent" />
      <Controls showLock={false} />
    </SvelteFlow>
  </div>
  <PipelineInspector {selectedId} />
</div>

<style>
  /* Inherit our dark tokens — override Svelte Flow's defaults. */
  div :global(.svelte-flow) {
    --xy-background-color: transparent;
    --xy-edge-stroke: var(--text3);
    --xy-edge-stroke-width: 1.5;
    --xy-handle-background-color: var(--primary);
    --xy-handle-border-color: var(--card);
  }
  div :global(.svelte-flow__controls button) {
    background: var(--card);
    border-color: var(--border);
    color: var(--foreground);
  }
  div :global(.svelte-flow__controls button:hover) {
    background: var(--secondary);
  }
  div :global(.svelte-flow__node) {
    font-family: var(--font-sans);
  }
  div :global(.svelte-flow__edge-path) {
    stroke: var(--text3);
  }
  div :global(.svelte-flow__edge.selected .svelte-flow__edge-path) {
    stroke: var(--primary);
  }
  div :global(.svelte-flow__arrowhead) {
    fill: var(--text3);
  }
</style>
