# My Legal Companion
---

This application aims at providing expert guidance on navigating complex laws and regulations, helping individuals and businesses manage risks, ensure compliance, and make informed decisions. Examples include corporate restructuring, intellectual property protection, contract drafting, employment law counseling, regulatory compliance audits, and tax advisory.

- Corporate & Business Services
- Employment & Human Resources
- Regulatory & Compliance
- Real Estate & Property
- Individuals & Personal Matters

Legal advisory is distinct from legal representation in court, focusing instead on proactive guidance to prevent litigation and ensure compliance. 

---

```mermaid
graph TB
    User@{ shape: circle, label: "User Request" } -->|Legal Problem| Adviser[Legal Adviser<br/>Orchestrator Agent]
    
    Adviser -->|Legal Advice| Evaluator[Evaluator<br/>Agent]
    
    subgraph Evaluation
    Evaluator --> Decision{Pass?}
    end

    Decision -->|Yes| Writer[Writer<br/>Agent]
    Decision -.Evaluation Report.-> Adviser

    Writer -->|Markdown Reports| DB@{ shape: cyl, label: "Database" }
    
    DB -->|Results| Response@{ shape: stadium, label: "Complete Analysis<br/>Report" }
    
    Adviser --->|Retrieve Context| Vectors[(S3 Vectors<br/>Knowledge Base)]
    
    Schedule[EventBridge<br/>Every Week] -->|Trigger| Researcher[Researcher<br/>Agent]
    Researcher -->|Store Legal Insights| Vectors
    Researcher -->|Web Research| Browser[Web Browser<br/>MCP Server]
    
    style Adviser fill:#155DFC,stroke:#333,stroke-width:3px
    style Evaluator fill:#FF5F15
    style Writer fill:#05DF72
    style Researcher fill:#C81CDE
```

## Agent Responsibilities

### Legal Advisor
**Role**: This is the main orchestrator agent. This agent interacts with the user and decides the next action steps.

### Evaluator
**Role**: This agent acts as a judge to evaluate the output from the Advisor agent above.

### Writer
**Role**: The writer agent receives the output from the evalutor once the output has passed the judgement and generates a report that will be sent to the user.

### Researcher (Independent Agent)
**Role**: Autonomously gather changes and new laws.
- Runs independently on EventBridge schedule (every week)
- Not orchestrated by any agent - operates autonomously
- Browses state and law society websites for changes 
- Continuously populates S3 Vectors knowledge base
- Knowledge is later retrieved by the Legal Adviser for context


## Future Agent Enhancements

## Technology Stack

- **Infrastructure**: Terraform
- **Compute**: Lambda, App Runner
- **AI/ML**: SageMaker, AWS Bedrock
- **Storage**: S3 Vectors
- **API**: API Gateway
- **Languages**: Python 3.12, TypeScript
- **Container**: Docker