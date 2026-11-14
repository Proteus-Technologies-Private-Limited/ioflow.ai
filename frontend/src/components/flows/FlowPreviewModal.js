import React, { useCallback, useMemo } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import '../flow/nodeStyles.css';
import {
  XMarkIcon,
  ClockIcon,
  ChartBarIcon,
  TagIcon,
} from '@heroicons/react/24/outline';
import { getColorClasses, getDifficultyBadge } from '../../utils/categoryIcons';

// Import custom node types (same as FlowDesigner)
import TriggerNode from '../flow/TriggerNode';
import ActionNode from '../flow/ActionNode';
import TransformNode from '../flow/TransformNode';
import ConditionNode from '../flow/ConditionNode';
import ResponseNode from '../flow/ResponseNode';
import LoopNode from '../flow/LoopNode';

const nodeTypes = {
  trigger: TriggerNode,
  action: ActionNode,
  transform: TransformNode,
  condition: ConditionNode,
  response: ResponseNode,
  loop: LoopNode,
};

const FlowPreviewModal = ({ open, onClose, example, flowData }) => {
  // Extract flow definition
  const flowDefinition = useMemo(() => {
    if (!flowData) return { nodes: [], edges: [] };

    // Try different locations for flow definition
    if (flowData.flow && flowData.flow.flow_definition) {
      return flowData.flow.flow_definition;
    }
    if (flowData.flow_definition) {
      return flowData.flow_definition;
    }
    return { nodes: [], edges: [] };
  }, [flowData]);

  // Prepare nodes and edges for ReactFlow
  const nodes = useMemo(() => {
    if (!flowDefinition.nodes) return [];

    return flowDefinition.nodes.map(node => ({
      ...node,
      draggable: false,
      selectable: false,
      connectable: false,
    }));
  }, [flowDefinition]);

  const edges = useMemo(() => {
    if (!flowDefinition.edges) return [];

    return flowDefinition.edges.map(edge => ({
      ...edge,
      animated: false,
      selectable: false,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 20,
        height: 20,
      },
    }));
  }, [flowDefinition]);

  // Get color classes for the category
  const colorClasses = example ? getColorClasses(example.color) : {};
  const difficultyBadge = example ? getDifficultyBadge(example.difficulty) : {};

  if (!example) return null;

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-[100] overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white shadow-xl transition-all w-full max-w-7xl h-[90vh] flex flex-col">
                {/* Header */}
                <div className={`px-6 py-4 border-b border-gray-200 bg-gradient-to-r ${colorClasses.gradient}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <Dialog.Title as="h3" className={`text-xl font-semibold ${colorClasses.text}`}>
                          {example.name}
                        </Dialog.Title>
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                            difficultyBadge.color === 'green'
                              ? 'bg-green-100 text-green-800'
                              : difficultyBadge.color === 'yellow'
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {difficultyBadge.label}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 mb-3">{example.description}</p>

                      {/* Metadata */}
                      <div className="flex flex-wrap gap-4 text-xs text-gray-600">
                        <div className="flex items-center gap-1">
                          <ClockIcon className="h-4 w-4" />
                          <span>{example.estimated_time}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <ChartBarIcon className="h-4 w-4" />
                          <span>{example.import_count} imports</span>
                        </div>
                        {example.average_rating && (
                          <div className="flex items-center gap-1">
                            <span className="text-yellow-500">★</span>
                            <span>{example.average_rating} ({example.rating_count} ratings)</span>
                          </div>
                        )}
                      </div>

                      {/* Tags */}
                      <div className="flex flex-wrap gap-2 mt-3">
                        {example.tags.map((tag, index) => (
                          <span
                            key={index}
                            className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${colorClasses.badge}`}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Close button */}
                    <button
                      type="button"
                      className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none ml-4"
                      onClick={onClose}
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>
                </div>

                {/* Flow Diagram */}
                <div className="flex-1 bg-gray-50">
                  {nodes.length > 0 ? (
                    <ReactFlow
                      nodes={nodes}
                      edges={edges}
                      nodeTypes={nodeTypes}
                      fitView
                      nodesDraggable={false}
                      nodesConnectable={false}
                      elementsSelectable={false}
                      zoomOnScroll={true}
                      panOnScroll={false}
                      zoomOnDoubleClick={false}
                      preventScrolling={false}
                    >
                      <Background color="#aaa" gap={16} />
                      <Controls showInteractive={false} />
                      <MiniMap
                        nodeColor={(node) => {
                          switch (node.type) {
                            case 'trigger':
                              return '#10b981';
                            case 'action':
                              return '#3b82f6';
                            case 'condition':
                              return '#f59e0b';
                            case 'transform':
                              return '#8b5cf6';
                            case 'response':
                              return '#ec4899';
                            case 'loop':
                              return '#06b6d4';
                            default:
                              return '#6b7280';
                          }
                        }}
                        maskColor="#f3f4f650"
                      />
                    </ReactFlow>
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <div className="text-center text-gray-500">
                        <p className="text-lg font-medium">No flow diagram available</p>
                        <p className="text-sm mt-2">This example doesn't have a visual flow definition</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-600">
                      <span className="font-medium">Category:</span> {example.category}
                    </div>
                    <button
                      type="button"
                      onClick={onClose}
                      className="inline-flex justify-center rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                    >
                      Close Preview
                    </button>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default FlowPreviewModal;
