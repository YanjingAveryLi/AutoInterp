# AutoInterp System Workflow & Architecture

## System Overview

AutoInterp is an automated AI interpretability research framework that uses multiple LLM agents to generate, test, and evaluate questions about language model behavior. The system follows a comprehensive 5-phase pipeline with iterative analysis cycles and integrated visualization generation.

## Step-by-Step Workflow

### **Phase 1: Question Generation**
**Component:** `QuestionManager` (using `question_generator` agent)

1. **Input:** Task description from config (`task.description`)
2. **Process:** LLM generates multiple specific, testable questions about model behavior
3. **Output:** Raw text saved to `questions.txt`
4. **Prompt Structure:**
   - System: Expert interpretability researcher, no markdown
   - User: Task description + requirements for specific, testable questions
   - Focus: Internal mechanisms, activation patterns, no training/fine-tuning

### **Phase 2: Question Prioritization** 
**Component:** `QuestionManager` (using `question_prioritizer` agent)

1. **Input:** Raw questions text from Phase 1
2. **Process:** LLM selects most promising question based on specificity, testability, and value
3. **Output:** Structured text with QUESTION, RATIONALE, PROCEDURE, TITLE fields
4. **Side Effect:** Project renamed using TITLE field with timestamp
5. **Prompt Structure:**
   - System: Expert researcher for prioritization, plain text only
   - User: All questions + selection criteria
   - Output: Structured fields for selected question

### **Phase 3: Iterative Analysis & Evaluation**
**Components:** `AnalysisPlanner`, `AnalysisGenerator`, `AnalysisExecutor`, `Evaluator`

#### **3a: Analysis Planning**
**Component:** `AnalysisPlanner` (using `analysis_planner` agent)

1. **Input:** 
   - Prioritized question text
   - Previous evaluation results (if any)
2. **Process:** Creates detailed plan for next analysis step
3. **Output:** Structured plan with PURPOSE, METHODS, EXPECTED OUTPUTS
4. **Prompt Structure:**
   - System: Analysis planner for interpretability research
   - User: Question + evaluation history + plan format requirements

#### **3b: Code Generation**
**Component:** `AnalysisGenerator` (using `analysis_generator` agent)

1. **Input:**
   - Question text
   - Analysis plan from 3a
   - Model configuration
   - Error context (if retry)
2. **Process:** Generates Python analysis code
3. **Output:** Executable analysis script
4. **Prompt Structure:**
   - System: Expert Python programmer, code-only output
   - User: Specification with question, model, plan + requirements
   - Focus: print to stdout, no visualizations

#### **3c: Code Execution**
**Component:** `AnalysisExecutor`

1. **Input:** Generated Python script
2. **Process:** 
   - Executes in isolated virtual environment
   - Captures stdout/stderr
   - Auto-installs missing modules
   - Retries on failure (up to max_retries)
3. **Output:** Execution results with stdout as primary data
4. **Error Handling:** Automatic module detection/installation, graceful failure

#### **3d: Result Evaluation**
**Component:** `Evaluator` (using `evaluator` agent)

1. **Input:**
   - Analysis results (stdout/stderr)
   - Original question
   - Script content
2. **Process:** LLM evaluates results against question
3. **Output:** 
   - Raw evaluation text
   - NEW_CONFIDENCE value (0-1)
   - Insights and recommendations
4. **Prompt Structure:**
   - System: Expert interpretability researcher for evaluation
   - User: Question + script + outputs + evaluation criteria

#### **3e: Iteration Control**
**Logic:** Continue until confidence threshold reached OR max iterations

- **Continue if:** `confidence_threshold > confidence`
- **Stop if:** High confidence (≥0.85) or max iterations reached
- **Next iteration:** Reset analysis generator, increment cycle counter

### **Phase 4: Visualization Generation & Evaluation**
**Components:** `VisualizationPlanner`, `VisualizationGenerator`, `VisualizationEvaluator`

1. **Input:**
   - Successful analysis results
   - Analysis scripts and outputs
2. **Process:**
   - Plans appropriate visualizations for each successful analysis
   - Generates Python visualization code
   - Executes visualization scripts in sandboxed environment
   - Evaluates generated visualizations with multimodal LLM analysis
   - Retries visualization generation if issues are detected
3. **Output:**
   - Visualization images (PNG, JPG, SVG, PDF)
   - Visualization evaluation reports
   - Organized visualization files with analysis prefixes

### **Phase 5: Report Generation**
**Component:** `ReportGenerator`

1. **Input:**
   - Final question text
   - All analysis results
   - All evaluation results
   - Generated visualizations
2. **Process:** Compiles comprehensive markdown report with visualizations
3. **Output:** Final report with conclusion, confidence, insights, and visual evidence

## Prompt Structure Summary

| Component | Agent | System Message | User Prompt Inputs | Output Format |
|-----------|-------|----------------|-------------------|---------------|
| Question Generator | `question_generator` | Expert researcher, plain text | Task description | Raw numbered questions |
| Question Prioritizer | `question_prioritizer` | Expert prioritizer, plain text | All questions | QUESTION/RATIONALE/PROCEDURE/TITLE |
| Analysis Planner | `analysis_planner` | Analysis design expert | Question + evaluations | PURPOSE/METHODS/OUTPUTS |
| Analysis Generator | `analysis_generator` | Python expert, code only | Question + plan + model | Executable Python code |
| Evaluator | `evaluator` | Evaluation expert | Question + script + results | Raw evaluation + NEW_CONFIDENCE |
| Visualization Planner | `visualization_planner` | Visualization design expert | Analysis script + output | Visualization plan |
| Visualization Generator | `visualization_generator` | Python/viz expert, code only | Analysis script + output + plan | Executable visualization code |
| Visualization Evaluator | `visualization_evaluator` | Multimodal evaluation expert | Viz code + generated image | Quality assessment + issues |


## File Structure During Execution

```
projects/{project_name}_{timestamp}/
├── questions/
│   ├── questions.txt                    # Raw generated questions
│   └── prioritized_question.txt       # Selected question
├── analysis_plans/
│   └── analysis_plan_{timestamp}.txt    # Analysis plans
├── analysis_scripts/
│   └── analysis_{n}/
│       └── attempt_{m}/
│           ├── analysis_{timestamp}.py  # Generated code
│           ├── stdout.txt              # Execution output
│           └── stderr.txt              # Error output
├── evaluation_results/
│   └── eval_{id}_{timestamp}/
│       └── evaluation_{timestamp}.txt  # Evaluation results
├── visualizations/
│   ├── a{n}_{viz_name}_{timestamp}.png # Generated visualizations (images)
│   ├── visualization_{analysis}_{timestamp}.py # Visualization scripts
│   └── visualization_{analysis}_{timestamp}_retry{n}.py # Retry attempts
├── logs/
│   ├── a{n}.{m}_viz_evaluation_{timestamp}.txt # Visualization evaluations
│   ├── console.log                     # Console output log
│   └── comprehensive.log               # Complete system log
└── reports/
    └── final_report.md                  # Final comprehensive report with visualizations
```

By default the `projects` root is placed inside `projects/` at the repository root when launching the package. Pass `--projects-dir` to the CLI to store runs elsewhere.

The system emphasizes simplicity, using raw text files instead of complex structured data, while maintaining robust error handling and iterative refinement of questions through multiple analysis cycles. Enhanced with comprehensive visualization generation and multimodal evaluation capabilities, the framework provides both analytical insights and visual evidence for interpretability research findings.
