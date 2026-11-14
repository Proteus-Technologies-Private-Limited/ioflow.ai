import React, { useState, useRef, useEffect, useMemo } from 'react';
import Joyride, { STATUS, ACTIONS, EVENTS } from 'react-joyride';

/**
 * Custom Tooltip Component with Drag Support
 */
const DraggableTooltip = ({
  continuous,
  index,
  step,
  backProps,
  closeProps,
  primaryProps,
  skipProps,
  tooltipProps,
  isLastStep,
}) => {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const tooltipRef = useRef(null);

  const handleMouseDown = (e) => {
    // Only allow dragging from the header area
    if (e.target.closest('.tutorial-drag-handle')) {
      setIsDragging(true);
      setDragStart({
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, dragStart]);

  // Reset position when step changes
  useEffect(() => {
    setPosition({ x: 0, y: 0 });
  }, [index]);

  return (
    <div
      {...tooltipProps}
      ref={tooltipRef}
      style={{
        ...tooltipProps.style,
        backgroundColor: 'white',
        borderRadius: '8px',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        maxWidth: '400px',
        padding: 0,
        transform: `translate(${position.x}px, ${position.y}px)`,
        cursor: isDragging ? 'grabbing' : 'default',
      }}
    >
      {/* Draggable Header */}
      <div
        className="tutorial-drag-handle"
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #e5e7eb',
          cursor: 'grab',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#f9fafb',
          borderTopLeftRadius: '8px',
          borderTopRightRadius: '8px',
        }}
        onMouseDown={handleMouseDown}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ opacity: 0.5 }}
          >
            <circle cx="4" cy="4" r="1" fill="currentColor" />
            <circle cx="8" cy="4" r="1" fill="currentColor" />
            <circle cx="12" cy="4" r="1" fill="currentColor" />
            <circle cx="4" cy="8" r="1" fill="currentColor" />
            <circle cx="8" cy="8" r="1" fill="currentColor" />
            <circle cx="12" cy="8" r="1" fill="currentColor" />
            <circle cx="4" cy="12" r="1" fill="currentColor" />
            <circle cx="8" cy="12" r="1" fill="currentColor" />
            <circle cx="12" cy="12" r="1" fill="currentColor" />
          </svg>
          <span style={{ fontSize: '12px', color: '#6b7280', fontWeight: '500' }}>
            Drag to move • Step {index + 1}
          </span>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: '20px 16px' }}>
        {step.content}
      </div>

      {/* Footer with buttons */}
      <div
        style={{
          padding: '12px 16px',
          borderTop: '1px solid #e5e7eb',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <button
          {...skipProps}
          style={{
            background: 'none',
            border: 'none',
            color: '#9ca3af',
            cursor: 'pointer',
            fontSize: '14px',
            padding: '4px 8px',
          }}
        >
          Skip tutorial
        </button>
        <div style={{ display: 'flex', gap: '8px' }}>
          {index > 0 && (
            <button
              {...backProps}
              style={{
                background: 'none',
                border: 'none',
                color: '#6b7280',
                cursor: 'pointer',
                fontSize: '14px',
                padding: '8px 16px',
              }}
            >
              Back
            </button>
          )}
          <button
            {...primaryProps}
            style={{
              backgroundColor: '#3b82f6',
              border: 'none',
              borderRadius: '6px',
              color: 'white',
              cursor: 'pointer',
              fontSize: '14px',
              padding: '8px 16px',
              fontWeight: '500',
            }}
          >
            {isLastStep ? 'Finish' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * FlowTutorial Component
 * Provides an interactive guided tutorial for first-time users
 * Uses react-joyride for the guided tour experience
 * Now with conditional steps based on user selections
 */
const FlowTutorial = ({ run, onComplete }) => {
  const [stepIndex, setStepIndex] = useState(0);
  const [selectedTriggerType, setSelectedTriggerType] = useState(null);
  const [hasActionNode, setHasActionNode] = useState(false);

  // Monitor DOM for user selections
  useEffect(() => {
    if (!run) return;

    const checkTriggerType = () => {
      // Check selected trigger node
      const triggerNodes = document.querySelectorAll('.react-flow__node-trigger');
      if (triggerNodes.length > 0) {
        // Try to detect trigger type from the node
        const triggerNode = triggerNodes[0];
        const triggerText = triggerNode.textContent;

        if (triggerText.includes('Manual')) {
          setSelectedTriggerType('manual');
        } else if (triggerText.includes('Event')) {
          setSelectedTriggerType('application_event');
        } else if (triggerText.includes('Webhook')) {
          setSelectedTriggerType('webhook');
        } else if (triggerText.includes('Schedule')) {
          setSelectedTriggerType('schedule');
        }
      }
    };

    const checkActionNode = () => {
      const actionNodes = document.querySelectorAll('.react-flow__node-action');
      setHasActionNode(actionNodes.length > 0);
    };

    const observer = new MutationObserver(() => {
      checkTriggerType();
      checkActionNode();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    checkTriggerType();
    checkActionNode();

    return () => observer.disconnect();
  }, [run]);

  // Base steps that are always shown
  const baseSteps = [
    {
      target: '.react-flow__node-trigger',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Welcome to IOFlow! 👋</h3>
          <p className="mb-2">
            Let's build your first automated flow in just a few simple steps.
          </p>
          <p className="text-sm text-gray-600 mb-2">
            <strong>Step 1: Click on the Trigger Node</strong>
          </p>
          <p className="text-sm text-gray-600">
            A trigger node has been created for you (the green box). Click on it to open the configuration panel on the right.
          </p>
        </div>
      ),
      placement: 'right',
      disableBeacon: true,
      spotlightClicks: true,
    },
    {
      target: 'body',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Select Trigger Type ⚙️</h3>
          <p className="mb-2">
            <strong>Step 2: Choose How Your Flow Starts</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            In the properties panel on the right, find <strong>Trigger Configuration</strong> and select a trigger type:
          </p>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            <li><strong>Manual</strong> - Trigger manually with custom variables</li>
            <li><strong>Webhook</strong> - Trigger via HTTP webhook</li>
            <li><strong>Schedule</strong> - Trigger on a schedule (cron)</li>
            <li><strong>Application Event</strong> - Trigger from an app event</li>
          </ul>
          <p className="text-xs text-blue-600 mt-2">
            💡 The tutorial will adapt based on your selection!
          </p>
        </div>
      ),
      placement: 'center',
      disableBeacon: true,
      spotlightClicks: true,
    },
    {
      target: '.flow-add-node-button',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Add an Action Node 🎯</h3>
          <p className="mb-2">
            <strong>Step 3: Add an Action</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            Click the <strong>+ Add Node</strong> button, then select <strong>Action</strong> from the menu.
          </p>
          <p className="text-sm text-gray-600">
            Actions perform tasks like sending emails, creating records, calling APIs, processing data, and much more.
          </p>
        </div>
      ),
      placement: 'right',
      spotlightClicks: true,
    },
    {
      target: 'body',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Click on the Action Node 📍</h3>
          <p className="mb-2">
            <strong>Step 4: Open Action Configuration</strong>
          </p>
          <p className="text-sm text-gray-600">
            After the action node appears on the canvas (blue box), click on it to open its configuration panel on the right.
          </p>
        </div>
      ),
      placement: 'center',
      spotlightClicks: true,
    },
    {
      target: 'body',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Select Application 📱</h3>
          <p className="mb-2">
            <strong>Step 5: Choose Your Application</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            In the properties panel, find the <strong>Application</strong> dropdown and select the app you want to use (e.g., Gmail, Slack, Salesforce, etc.).
          </p>
          <p className="text-sm text-gray-600">
            This determines which services and operations will be available.
          </p>
        </div>
      ),
      placement: 'center',
      spotlightClicks: true,
    },
    {
      target: 'body',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Select Service 🔧</h3>
          <p className="mb-2">
            <strong>Step 6: Choose Your Service</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            After selecting an application, a <strong>Service</strong> dropdown will appear. Select the specific operation you want to perform.
          </p>
          <p className="text-sm text-gray-600">
            For example: "Send Email", "Create Record", "Get Data", etc.
          </p>
        </div>
      ),
      placement: 'center',
      spotlightClicks: true,
    },
    {
      target: 'body',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Configure Service Parameters 🔗</h3>
          <p className="mb-2">
            <strong>Step 7: Map Your Data</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            After selecting a service, you'll see parameter fields. Use the <strong>+ button</strong> next to each field to map data from your trigger or previous nodes.
          </p>
          <p className="text-sm text-gray-600">
            This connects information between steps. For example, use an email from a webhook trigger to send a notification.
          </p>
        </div>
      ),
      placement: 'center',
      spotlightClicks: true,
    },
    {
      target: '.bg-blue-600',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Save Your Flow 🚀</h3>
          <p className="mb-2">
            <strong>Step 8: Save and Activate</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            Click the <strong>Save</strong> button to save your flow. Once saved, you can activate it to start processing triggers!
          </p>
          <div className="mt-3 p-2 bg-blue-50 rounded text-xs space-y-1">
            <div>💡 <strong>Pro tip:</strong> Use Transform nodes to manipulate data between actions</div>
            <div>🔄 <strong>Tip:</strong> Connect nodes by dragging from the dots on node edges</div>
            <div>⚡ <strong>Help:</strong> Press <strong>?</strong> anytime to restart this tutorial</div>
          </div>
        </div>
      ),
      placement: 'bottom',
      spotlightClicks: false,
    },
  ];

  // Conditional steps for Manual Trigger
  const manualTriggerSteps = [
    {
      target: 'body',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Add Manual Variables 📝</h3>
          <p className="mb-2">
            <strong>Manual Trigger Configuration</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            Since you selected <strong>Manual</strong> trigger, you can define custom variables that will be provided when manually triggering the flow.
          </p>
          <p className="text-sm text-gray-600 mb-2">
            In the properties panel, you'll see a section to add manual variables. Click <strong>+ Add Variable</strong> to define:
          </p>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            <li><strong>Variable Name</strong> - e.g., "email", "userId"</li>
            <li><strong>Type</strong> - string, number, boolean, etc.</li>
            <li><strong>Description</strong> - What this variable is for</li>
          </ul>
          <p className="text-xs text-blue-600 mt-2">
            💡 These variables will be available in your actions!
          </p>
        </div>
      ),
      placement: 'center',
      spotlightClicks: true,
    },
  ];

  // Conditional steps for Application Event Trigger
  const applicationEventSteps = [
    {
      target: 'body',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Select Application 📱</h3>
          <p className="mb-2">
            <strong>Application Event - Step 1</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            Since you selected <strong>Application Event</strong> trigger, you need to choose which application will trigger this flow.
          </p>
          <p className="text-sm text-gray-600 mb-2">
            In the properties panel, find the <strong>Application</strong> dropdown and select an app (e.g., Gmail, Slack, Salesforce).
          </p>
          <p className="text-xs text-blue-600 mt-2">
            💡 This determines which events are available
          </p>
        </div>
      ),
      placement: 'center',
      spotlightClicks: true,
    },
    {
      target: 'body',
      content: (
        <div>
          <h3 className="text-lg font-semibold mb-2">Select Event 🔔</h3>
          <p className="mb-2">
            <strong>Application Event - Step 2</strong>
          </p>
          <p className="text-sm text-gray-600 mb-2">
            After selecting an application, an <strong>Event</strong> dropdown will appear with available events for that app.
          </p>
          <p className="text-sm text-gray-600 mb-2">
            Select the event that should trigger your flow, such as:
          </p>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            <li>"New Email Received"</li>
            <li>"New Message in Channel"</li>
            <li>"Record Created"</li>
            <li>etc.</li>
          </ul>
          <p className="text-xs text-blue-600 mt-2">
            💡 Event data will be available in your actions!
          </p>
        </div>
      ),
      placement: 'center',
      spotlightClicks: true,
    },
  ];

  // Build dynamic steps based on selections
  const steps = useMemo(() => {
    const dynamicSteps = [...baseSteps];

    // Insert conditional steps after step 2 (trigger type selection)
    const insertIndex = 2;

    if (selectedTriggerType === 'manual') {
      dynamicSteps.splice(insertIndex, 0, ...manualTriggerSteps);
    } else if (selectedTriggerType === 'application_event') {
      dynamicSteps.splice(insertIndex, 0, ...applicationEventSteps);
    }

    // Re-number the steps in the content
    return dynamicSteps.map((step, index) => ({
      ...step,
      content: React.cloneElement(step.content, {
        // This allows us to access the actual step number in tooltips
        'data-step-number': index + 1,
      }),
    }));
  }, [selectedTriggerType, baseSteps, manualTriggerSteps, applicationEventSteps]);

  const handleJoyrideCallback = (data) => {
    const { status, index, action } = data;

    // Tutorial finished or skipped
    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
      if (onComplete) {
        onComplete();
      }
    }

    // Track step index for conditional logic
    if (action === ACTIONS.NEXT || action === ACTIONS.PREV) {
      setStepIndex(index);
    }
  };

  return (
    <Joyride
      steps={steps}
      run={run}
      continuous
      showProgress={false}
      showSkipButton={false}
      callback={handleJoyrideCallback}
      tooltipComponent={DraggableTooltip}
      styles={{
        options: {
          primaryColor: '#3b82f6', // Blue-500
          zIndex: 10000,
          overlayColor: 'rgba(0, 0, 0, 0.2)', // More transparent background (was 0.5 default)
        },
        overlay: {
          backgroundColor: 'rgba(0, 0, 0, 0.2)', // More transparent overlay
        },
        spotlight: {
          backgroundColor: 'transparent',
        },
        tooltip: {
          borderRadius: 8,
          fontSize: 14,
        },
        tooltipContent: {
          padding: '20px 10px',
        },
        buttonNext: {
          backgroundColor: '#3b82f6',
          borderRadius: 6,
          padding: '8px 16px',
        },
        buttonBack: {
          color: '#6b7280',
          marginRight: 10,
        },
        buttonSkip: {
          color: '#9ca3af',
        },
      }}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Finish',
        next: 'Next',
        skip: 'Skip tutorial',
      }}
      floaterProps={{
        disableAnimation: false,
      }}
      scrollToFirstStep
      scrollOffset={100}
      disableOverlayClose
      spotlightPadding={5}
    />
  );
};

export default FlowTutorial;
