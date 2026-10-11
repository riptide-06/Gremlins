# ISO box (synthetic example)

department: iso
name: International Student Office
authority_order: federal > state > campus > department
updated: 2026-10-10
synthetic: yes

## 1. Facts

F-01 | F-1 undergraduates must enroll in at least 12 units every fall, winter, and spring quarter. | federal | 8 CFR 214.2(f)(6)(i)(B) | yes
F-02 | Dropping below 12 units without a Reduced Course Load (RCL) authorization approved in advance is a status violation. | federal | 8 CFR 214.2(f)(6)(iii) | yes
F-03 | An RCL for a documented medical condition may be approved for up to 12 months total, and may reduce enrollment to zero units. | federal | 8 CFR 214.2(f)(6)(iii)(B) | yes
F-04 | An RCL for academic difficulty (initial difficulty with English, reading requirements, or US teaching methods) is allowed once per program level and requires at least 6 units. | federal | 8 CFR 214.2(f)(6)(iii)(A) | yes
F-05 | In the final quarter of a program, an F-1 student may enroll only in the units needed to complete the degree, with an RCL for final term approved by ISO. | federal | 8 CFR 214.2(f)(6)(iii)(C) | yes
F-06 | On-campus employment is limited to 20 hours per week while school is in session. | federal | 8 CFR 214.2(f)(9)(i) | yes
F-07 | ISO processes RCL requests within 5 business days of receiving the academic adviser's form and, for medical RCL, a licensed clinician's letter. | department | ISO internal SLA 2026 | yes
F-08 | Summer quarter is a vacation quarter; F-1 students are not required to enroll in summer unless summer is their first or final quarter. | federal | 8 CFR 214.2(f)(5)(iii) | yes
F-09 | Only one online or distance class (3 units) may count toward the 12-unit minimum each quarter. | federal | 8 CFR 214.2(f)(6)(i)(G) | yes
F-10 | Students on OPT must report employer changes within 10 days. | federal | 8 CFR 214.2(f)(12) | no

## 2. Precedence

P-01 | Federal immigration regulation overrides campus enrollment policy for F-1 status questions. | federal | campus
P-02 | Campus policy overrides departmental practice where they conflict. | campus | department

## 3. FAQ

Q-01 | Can I drop to 8 units this quarter? | Not without an approved RCL before you drop. An academic-difficulty RCL needs at least 6 units and is allowed once per program level [F-02] [F-04]. A medical RCL has no unit floor but needs a clinician's letter [F-03].
Q-02 | Do I have to take classes in summer? | No, unless summer is your first or final quarter [F-08].
Q-03 | How long does an RCL take? | About 5 business days after ISO receives the complete forms [F-07].

## 4. Escalation

E-01 | Medical or disability basis for a reduced load; a licensed clinician must be involved. | question ~ medical|illness|health|disab|mental
E-02 | Final quarter with a partial load; the degree audit must confirm remaining units. | final_quarter == yes and units < 12
E-03 | Student already below the full-time minimum without an RCL on file; this may already be a status violation. | units < 12 and rcl_on_file != yes
E-04 | Work hours above the on-campus limit. | hours > 20

## 5. Session log
