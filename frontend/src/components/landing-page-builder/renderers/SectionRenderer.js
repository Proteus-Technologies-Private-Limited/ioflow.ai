import React from 'react';
import HeroSection from './HeroSection';
import TextSection from './TextSection';
import ImageSection from './ImageSection';
import ImageGallerySection from './ImageGallerySection';
import TriggerFormSection from './TriggerFormSection';
import ExecutionDisplaySection from './ExecutionDisplaySection';
import ResultDisplaySection from './ResultDisplaySection';
import DocumentationSection from './DocumentationSection';
import FeaturesSection from './FeaturesSection';
import ColumnsSection from './ColumnsSection';
import SpacerSection from './SpacerSection';
import DividerSection from './DividerSection';
import CTAButtonSection from './CTAButtonSection';
import PricingSection from './PricingSection';
import ExecutionsListSection from './ExecutionsListSection';
import TaskInboxSection from './TaskInboxSection';

/**
 * SectionRenderer - Maps a section definition to the appropriate component
 */
export default function SectionRenderer({ section, sharedProps }) {
  const { type, config, id } = section;

  const scrollRef = (el) => {
    if (el && sharedProps.sectionRefs) {
      sharedProps.sectionRefs.current[id] = el;
    }
  };

  const handleCTAClick = (targetId) => {
    if (targetId && sharedProps.sectionRefs?.current?.[targetId]) {
      sharedProps.sectionRefs.current[targetId].scrollIntoView({ behavior: 'smooth' });
    }
  };

  const renderContent = () => {
    switch (type) {
      case 'hero':
        return <HeroSection config={config} onCTAClick={handleCTAClick} />;

      case 'text':
        return <TextSection config={config} />;

      case 'image':
        return <ImageSection config={config} />;

      case 'image_gallery':
        return <ImageGallerySection config={config} />;

      case 'trigger_form':
        return (
          <TriggerFormSection
            config={config}
            manualVariables={sharedProps.manualVariables}
            formData={sharedProps.formData}
            onFieldChange={sharedProps.onFieldChange}
            onSubmit={sharedProps.onSubmit}
            executing={sharedProps.executing}
            slug={sharedProps.slug}
            previewMode={sharedProps.previewMode}
            relatedFlows={sharedProps.relatedFlows}
            prerequisiteStatuses={sharedProps.prerequisiteStatuses}
            prerequisiteOutputs={sharedProps.prerequisiteOutputs}
            onRunPrerequisite={sharedProps.onRunPrerequisite}
            onSkipPrerequisite={sharedProps.onSkipPrerequisite}
            allPrerequisitesComplete={sharedProps.allPrerequisitesComplete}
            followupStatuses={sharedProps.followupStatuses}
            onRunFollowup={sharedProps.onRunFollowup}
            finalResult={sharedProps.finalResult}
            executionStatus={sharedProps.executionStatus}
          />
        );

      case 'execution_display':
        return (
          <ExecutionDisplaySection
            config={config}
            executionStatus={sharedProps.executionStatus}
            executionLogs={sharedProps.executionLogs}
            executing={sharedProps.executing}
            executionError={sharedProps.executionError}
            nodeStatus={sharedProps.nodeStatus}
            currentNode={sharedProps.currentNode}
            nodeExecutionData={sharedProps.nodeExecutionData}
            executedNodes={sharedProps.executedNodes}
            executingNodeId={sharedProps.executingNodeId}
            flowNodes={sharedProps.flowNodes}
            flowEdges={sharedProps.flowEdges}
            hitlTaskInfo={sharedProps.hitlTaskInfo}
            onHitlComplete={sharedProps.onHitlComplete}
            previewMode={sharedProps.previewMode}
          />
        );

      case 'result_display':
        return (
          <ResultDisplaySection
            config={config}
            finalResult={sharedProps.finalResult}
            executionStatus={sharedProps.executionStatus}
            previewMode={sharedProps.previewMode}
          />
        );

      case 'documentation':
        return (
          <DocumentationSection
            config={config}
            slug={sharedProps.slug}
            documentationPages={sharedProps.documentationPages}
            previewMode={sharedProps.previewMode}
          />
        );

      case 'features':
        return <FeaturesSection config={config} />;

      case 'columns':
        return (
          <ColumnsSection
            config={config}
            renderSection={(childSection) => (
              <SectionRenderer
                key={childSection.id}
                section={childSection}
                sharedProps={sharedProps}
              />
            )}
          />
        );

      case 'spacer':
        return <SpacerSection config={config} />;

      case 'divider':
        return <DividerSection config={config} />;

      case 'cta_button':
        return <CTAButtonSection config={config} onCTAClick={handleCTAClick} />;

      case 'pricing':
        return <PricingSection config={config} appInfo={sharedProps.appInfo} />;

      case 'executions_list':
        return (
          <ExecutionsListSection
            config={config}
            appInfo={sharedProps.appInfo}
            previewMode={sharedProps.previewMode}
          />
        );

      case 'task_inbox':
        return (
          <TaskInboxSection
            config={config}
            appInfo={sharedProps.appInfo}
            previewMode={sharedProps.previewMode}
          />
        );

      default:
        return (
          <div className="py-4 px-6 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
            Unknown section type: {type}
          </div>
        );
    }
  };

  // Hero section is full-width, others are contained
  const isFullWidth = type === 'hero';

  return (
    <div ref={scrollRef} id={id}>
      {isFullWidth ? (
        renderContent()
      ) : (
        <div className="px-4 sm:px-6">
          {renderContent()}
        </div>
      )}
    </div>
  );
}
