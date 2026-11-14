-- Create AI Transform Conversations table for tracking AI-assisted code generation conversations
CREATE TABLE IF NOT EXISTS ai_transform_conversations (
    conversation_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    tenant_id VARCHAR(50) NOT NULL,
    flow_id VARCHAR(50) NOT NULL,
    node_id VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active',
    flow_name VARCHAR(255),
    node_name VARCHAR(255),
    initial_context TEXT,
    message_count INTEGER DEFAULT 0,
    last_activity_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_ai_transform_conversations_user_flow_node 
ON ai_transform_conversations(user_id, flow_id, node_id);

CREATE INDEX IF NOT EXISTS idx_ai_transform_conversations_status 
ON ai_transform_conversations(status);

CREATE INDEX IF NOT EXISTS idx_ai_transform_conversations_last_activity 
ON ai_transform_conversations(last_activity_at);

-- Create AI Transform Messages table for storing conversation messages
CREATE TABLE IF NOT EXISTS ai_transform_messages (
    message_id VARCHAR(50) PRIMARY KEY,
    conversation_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    metadata TEXT, -- JSON string for additional data
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES ai_transform_conversations(conversation_id) ON DELETE CASCADE
);

-- Create index for faster message queries
CREATE INDEX IF NOT EXISTS idx_ai_transform_messages_conversation 
ON ai_transform_messages(conversation_id);

CREATE INDEX IF NOT EXISTS idx_ai_transform_messages_created 
ON ai_transform_messages(created_at);