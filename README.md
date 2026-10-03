![Status](https://img.shields.io/badge/status-complete-brightgreen)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red)


# AI Assisted Compliance Assessment Tool

A Proof of Concept (PoC) cybersecurity compliance assessment tool based on selected controls mapped to ISO/IEC 27001:2022 and the NIS2 Directive, with AI assisted interpretation of the results.

---

## Project Summary

This project was developed as the practical implementation of my diploma thesis on the use of artificial intelligence to support cybersecurity compliance assessments. The tool evaluates four selected cybersecurity control areas through predefined deterministic rules, with each control mapped to relevant requirements of ISO/IEC 27001:2022 and NIS2. 

Based on the information provided by the user, each control is assigned one of four assessment statuses: Satisfied, Partially Satisfied, Not Satisfied, or Not Assessable. The assessment results are then used to calculate a coverage score for the selected controls.  Artificial intelligence is integrated as an interpretation and reporting layer, using the completed assessment findings to generate a structured Executive Explanation for the user. The assessment logic, scoring, and framework mappings remain deterministic and predefined. The final results are presented through the Streamlit interface and can also be exported as a standalone HTML report.

---

## Security Controls Assessed

| Security Control | ISO/IEC 27001:2022 | NIS2 |
|---|---|---|
| Multi-Factor Authentication | A.8.5 – Secure authentication | Article 21(2)(j) |
| Backup and Restore Testing | A.8.13 – Information backup | Article 21(2)(c) |
| Vulnerability Management | A.8.8 – Management of technical vulnerabilities | Article 21(2)(e) |
| Incident Response Planning and Preparedness | A.5.24, A.5.26 | Article 21(2)(b) |


---

## Architecture & Assessment Workflow

The tool follows a structured assessment workflow that separates user input, deterministic evaluation, scoring, AI-assisted interpretation, and reporting.

1. **Organization Profile**  
   The user enters basic organization information such as name, size, number of employees, and sector.

2. **Security Control Assessment**  
   The user provides information for the four selected control areas:
   - Multi-Factor Authentication
   - Backup and Restore Testing
   - Vulnerability Management
   - Incident Response Planning and Preparedness

3. **Input Validation**  
   The submitted information is validated before being processed by the assessment engine.

4. **Deterministic Evaluation**  
   Predefined rules evaluate each security control and assign the appropriate assessment status.

5. **Scoring and Framework Mapping**  
   The assessment results are used to calculate the selected-controls coverage score, while each control is associated with its relevant ISO/IEC 27001:2022 and NIS2 requirements.

6. **AI Interpretation**  
   The completed assessment findings are provided to the AI layer, which generates a structured Executive Explanation of the results.

7. **Results and Reporting**  
   The application presents the assessment results through the Streamlit interface and generates a downloadable HTML report containing the detailed control findings, framework mappings, recommendations, evidence observations, and Executive Explanation(Overview, Management Interpretation, Priority Actions ,Information Gaps) .

![Assessment Architecture](images/arch-eng.png)

---

## How It Works

The assessment follows the following processing flow:

1. Organization and security-control information is entered through the Streamlit interface.
2. Input data is validated against a predefined JSON Schema.
3. The deterministic rule engine evaluates the four selected security controls.
4. Each control receives an assessment status.
5. The scoring component calculates the selected-controls coverage percentage.
6. Relevant ISO/IEC 27001 and NIS2 mappings are attached to the results.
7. The completed deterministic assessment is passed to the AI explanation layer.
8. AI generates a structured Executive Explanation based on the existing results.
9. The final assessment can be exported as an HTML report.

**Assessment decisions are made by deterministic rules rather than by the language model.**

---

## What I Implemented

- Built the application interface using **Streamlit**
- Created structured organization and security-control assessment forms
- Implemented **JSON Schema validation**
- Developed a deterministic rule engine for four cybersecurity control areas
- Implemented four assessment outcomes:
  - Satisfied
  - Partially Satisfied
  - Not Satisfied
  - Not Assessable
- Created a scoring mechanism that excludes Not Assessable controls from the denominator
- Created predefined mappings between selected **ISO/IEC 27001:2022** controls and **NIS2 Article 21** requirements
- Implemented control-specific rationales, recommendations, and evidence observations
- Integrated the **OpenAI API** for AI-assisted interpretation of assessment results
- Restricted AI to the explanation layer rather than the assessment decision process
- Added integrity checks around the deterministic assessment results
- Developed standalone HTML report generation using **Jinja2**
- Implemented automated tests for validation, rule evaluation, scoring, AI-result integrity, and report generation

---

## Screenshots

### Assessment Interface

![Assessment Interface](images/assessment-interface.png)

### Security Control Assessment

![Security Controls](images/security-controls.png)

### Assessment Summary

![Assessment Summary](images/assessment-summary.png)

### Detailed Control Results

![Detailed Results](images/detailed-results.png)

### Executive Explanation

![Executive Explanation](images/executive-explanation.png)

### HTML Assessment Report

![HTML Report](images/html-report.png)

🔎 Additional screenshots from the thesis evaluation scenarios are available in the [`images`](images/) folder.

---

## Example Assessment Scenarios

The tool was evaluated using synthetic organization scenarios to verify the assessment logic, scoring mechanism, AI-assisted explanation, and reporting process.

### Scenario 1 – Mixed Assessment

The first thesis evaluation scenario produced the following results:

- Multi-Factor Authentication — **Satisfied**
- Backup and Restore Testing — **Partially Satisfied**
- Vulnerability Management — **Not Satisfied**
- Incident Response Planning and Preparedness — **Not Assessable**

The Not Assessable control was excluded from the scoring denominator, resulting in a selected-controls coverage score of **50%**.

### Scenario 2 – Satisfied Controls

The second thesis evaluation scenario resulted in all four selected controls being assessed as **Satisfied**.

The assessment therefore produced:

- **4/4 assessable controls**
- **4/4 earned points**
- **100% selected-controls coverage**

---

## Tools & Technologies

- Python
- Streamlit
- OpenAI API
- JSON Schema
- Jinja2
- pandas
- pytest
- HTML / CSS
- Git & GitHub
- Visual Studio Code

---

## Project Structure

```text
AI-Assisted-Compliance-Assessment-Tool/
│
├── data/
│   ├── control_catalogue.json
│   ├── expected_results.json
│   ├── organization_schema.json
│   └── scenario_*.json
│
├── docs/
│   └── ARCHITECTURE_DECISIONS.md
│
├── images/
│
├── src/
│   ├── ai_summary.py
│   ├── form_adapter.py
│   ├── llm_provider.py
│   ├── models.py
│   ├── report_generator.py
│   ├── rule_engine.py
│   ├── scoring.py
│   └── validator.py
│
├── templates/
│   └── report_template.html
│
├── tests/
│   ├── test_ai_immutability.py
│   ├── test_form_adapter.py
│   ├── test_llm_provider.py
│   ├── test_report_generator.py
│   ├── test_rules.py
│   ├── test_scoring.py
│   └── test_validation.py
│
├── app.py
├── .env.example
├── .gitignore
├── requirements.txt
└── requirements-lock.txt
```

### Main Components

- `data/` – JSON Schema, framework mappings, synthetic scenarios, and expected deterministic results
- `docs/` – architecture and technical design decisions
- `images/` – application and assessment screenshots
- `src/` – deterministic assessment logic, scoring, AI integration, validation, and reporting
- `templates/` – HTML report template
- `tests/` – automated test suite
- `app.py` – Streamlit application entry point

---

## Running the Tool

Clone the repository:

```bash
git clone https://github.com/RakipGit/AI-Assisted-Compliance-Assessment-Tool.git
cd AI-Assisted-Compliance-Assessment-Tool
```

Create and activate a Python virtual environment.

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Create a local `.env` file based on `.env.example` and provide your OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5-mini
```

Run the Streamlit application:

```bash
streamlit run app.py
```

---

## Scope and Limitations

This project is a **Proof of Concept** and evaluates only four selected cybersecurity control areas.

The tool does not provide:

- ISO/IEC 27001 certification
- official NIS2 compliance confirmation
- audit assurance
- legal advice
- a complete assessment of an organization's cybersecurity posture

The assessment is based on user-provided information and does not independently verify supporting evidence.

The scoring model and selected evaluation thresholds are prototype design decisions and must not be interpreted as official ISO/IEC 27001 or NIS2 compliance metrics.

---

## Insights & Lessons Learned

- Separating deterministic assessment logic from AI-generated explanations improves reproducibility and transparency.
- AI can support the interpretation of cybersecurity compliance results without being responsible for the underlying assessment decision.
- Missing information should be distinguished from confirmed control failure, which led to the use of the **Not Assessable** status.
- Mapping related security controls between ISO/IEC 27001 and NIS2 helps demonstrate how common security practices can support requirements across different frameworks.
- Structured input validation is important before assessment logic is executed.
- Automated testing helps verify that rule evaluation, scoring, result integrity, and report generation behave consistently.
- A modular architecture makes it easier to separate validation, assessment, scoring, AI interpretation, and reporting responsibilities.

---

## Copyright Notice

All content and visuals in this repository are original and may not be reused without permission.


## Rakip 

ICT Engineering | Cybersecurity & Network Security

---
