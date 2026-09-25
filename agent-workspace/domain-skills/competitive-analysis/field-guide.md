# Field guide

One section per workbook column. The agent matches each column name against the `Matches:` regex
(case-insensitive, first match wins, so specific sections come before general ones), injects the
section into the prompt, and uses `Keywords:` to rank links worth opening.
All values: 2026-2027 academic year only (see `cycle-2026-2027.md`).

## School / College
Matches: ^school\s*/\s*college
Keywords: school, college, business
The name of the school or college within the university that runs the program, as the site writes it
(e.g. "Kelley School of Business", "Gies College of Business"). Not the university name.

## City
Matches: location\s*-\s*city
Keywords: contact, location, campus, about
City of the university's main campus / the school's address (e.g. "West Lafayette"). No state.

## State
Matches: location\s*-\s*state
Keywords: contact, location, campus, about
US state of that address, two-letter postal code (e.g. "IN").

## Delivery faculty
Matches: delivery model.*(faculty|adjunct)
Keywords: faculty, instructors, online, taught
Who teaches the online courses. Answer "Full-time faculty", "Part-time adjuncts" or "Mix", only if the page
says so (e.g. "taught by the same faculty as our on-campus program" = Full-time faculty).

## Delivery model
Matches: delivery model
Keywords: online, format, delivery, hybrid, residency, immersion
"100% online", "Hybrid" or "Online with required residency", as the page states. Mention required on-campus
residencies/immersions briefly (e.g. "Online with two 3-day residencies").

## On-campus options
Matches: on-campus options
Keywords: residency, immersion, campus, visit, on-campus, in-person
Whether online students can (or must) come to campus: immersions, residencies, orientation weekends,
option to take on-campus courses. Answer "Yes" / "No" plus a few words ("Yes - optional 3-day immersion").

## GMAT/GRE required
Matches: gmat/gre required|test required
Keywords: admission, requirements, gmat, gre, waiver, test
"Yes", "No" or "Waivable" (and the waiver condition in a few words), for applicants to this program.

## GMAT
Matches: average gmat
Keywords: class profile, gmat, students, profile, admission statistics
Average (mean) GMAT of the entering 2026-2027 class, e.g. "640". Median only if labelled median
(write "640 (median)"). A minimum or range is not an average. If tests are not required and no average is
published -> not found.

## GRE
Matches: average gre
Keywords: class profile, gre, students, profile
Average GRE of the entering class; keep the page's format ("Verbal 155, Quant 158" or "313").

## GPA
Matches: undergraduate gpa|\bgpa\b
Keywords: class profile, gpa, students, profile
Average undergraduate GPA of the entering class, e.g. "3.4". A minimum admission GPA is not an average.

## Work experience
Matches: work experience
Keywords: class profile, experience, students, profile
Average years or months of work experience of the entering class, converted by the page's own figure:
write months (e.g. page says "6 years" -> "72"). Only convert years to months; nothing else.

## Age
Matches: student age|\bage\b
Keywords: class profile, age, students
Average age of the entering class, e.g. "32".

## Class size
Matches: class size
Keywords: class profile, cohort, students, enrolled
Number of students in the entering class / cohort (not total enrollment across years unless that is the
only "class size" stated).

## International share
Matches: international \(%\)|international %
Keywords: class profile, international, students
Percentage of international students in the class, e.g. "12%".

## Female share
Matches: female|women
Keywords: class profile, women, female, students
Percentage of women in the class, e.g. "41%".

## Acceptance rate
Matches: accept rate|acceptance
Keywords: class profile, admission statistics, acceptance
Share of applicants admitted, e.g. "65%".

## Total enrollment
Matches: total enrollment
Keywords: enrollment, students, profile
Total number of students currently enrolled in the program (all cohorts).

## Conferrals
Matches: conferrals
Keywords: degrees awarded, graduates, conferred
Average number of degrees conferred per year over the past 3 years, only if the site publishes it.

## Duration
Matches: duration|time commitment
Keywords: curriculum, duration, months, complete, length, format
Typical time to finish, in months (e.g. "as few as 20 months" -> "20"; "2 years" -> "24").
If a range is stated keep it ("18-36").

## Credit hours
Matches: credit hours|credits
Keywords: curriculum, credits, credit hours, courses, plan of study
Total credit hours to graduate, e.g. "36". Units, not courses (unless the page gives only courses; then
write "12 courses").

## Deadlines
Matches: deadline
Keywords: deadline, deadlines, apply, application, dates, admission
Application deadlines for terms starting **Fall 2026, Spring 2027 or Summer 2027**, all rounds, one
string: "Fall 2026: Round 1 Mar 1, 2026; Final Jul 15, 2026; Spring 2027: Nov 15, 2026".
Deadlines for Fall 2027 starts belong to 2027-2028 and are rejected. "Rolling admissions" is a valid
answer when the page says so.

## Experiential learning (Yes/No)
Matches: experiential learning.*yes/no
Keywords: experiential, capstone, consulting project, practicum, projects, curriculum
"Yes" if the program offers experiential learning (capstone with a real company, consulting project,
practicum, global immersion, internships), else "No" only if the page makes clear there is none.

## Experiential learning (description)
Matches: experiential learning.*description
Keywords: experiential, capstone, consulting project, practicum
One or two sentences naming the opportunities, from the page wording.

## Affinity groups (Yes/No)
Matches: affinity groups.*yes/no
Keywords: clubs, student organizations, affinity, diversity, community, inclusion
"Yes" if there are identity-based student groups/associations open to this program's students
(women in business, Black/Hispanic/LGBTQ+/veteran/international student associations), else "No"
only if clearly stated.

## Affinity groups (description)
Matches: affinity groups.*description
Keywords: clubs, student organizations, affinity, diversity
The group names, comma separated, from the page.

## 3-year degree from India
Matches: 3.?yr|three.?year|india
Keywords: international, requirements, degree, equivalency, three-year, admission
"Y" if the school accepts a three-year bachelor's degree from India (sometimes only with conditions: say
"Y - with WES evaluation" etc.), "N" if it requires a four-year / 16-year-education equivalent.
Look on the international applicant requirements page.

## Career coaching (Yes/No)
Matches: career coaching.*yes/no
Keywords: career, coaching, career services, advising
"Yes" if online students get career coaching/advising/consulting services, else "No" only if clearly stated.

## Tuition per credit - in-state
Matches: in-state tuition per credit
Keywords: tuition, cost, per credit, fees, bursar, rates
2026-2027 tuition per credit hour for in-state (resident) students, e.g. "$1,250". If the online program
has one rate for everyone, that rate.

## Tuition per credit - out-of-state
Matches: out-of-state tuition per credit
Keywords: tuition, cost, per credit, fees, bursar, rates, nonresident
2026-2027 tuition per credit hour for out-of-state (nonresident) students.

## Tuition per credit - international
Matches: international tuition per credit
Keywords: tuition, cost, per credit, international, fees
2026-2027 tuition per credit hour for international students (often the nonresident rate).

## Tuition total - in-state
Matches: in-state tuition total
Keywords: tuition, cost, total, program cost
Total 2026-2027 program tuition for in-state students as stated by the page ("$38,400 total").
Never multiply per-credit by credits yourself.

## Tuition total - out-of-state
Matches: out-of-state tuition total
Keywords: tuition, cost, total, program cost, nonresident
Total program tuition for out-of-state students, as stated.

## Tuition total - international
Matches: international tuition total
Keywords: tuition, cost, total, international
Total program tuition for international students, as stated.

## Scholarship
Matches: scholarship
Keywords: scholarship, financial aid, funding, fellowships, tuition
Scholarships available to this program's 2026-2027 students: names and amounts if given
("Dean's Scholarship up to $10,000; Military tuition discount 10%"). "None" only if stated.

## Deposit required
Matches: deposit required
Keywords: deposit, enrollment deposit, admitted, confirm
"Yes"/"No": must admitted students pay an enrollment deposit?

## Deposit
Matches: deposit
Keywords: deposit, enrollment deposit, admitted, confirm, seat
Amount of the enrollment / seat deposit, e.g. "$500".

## Ranking - U.S. News
Matches: u\.?s\.? news
Keywords: rankings, ranked, us news, recognition
The program's U.S. News rank, with edition ("#12, 2026 Best Online Programs"). If the school does not cite it,
take it from usnews.com itself and keep the usnews.com page as the source link.
Only 2026 or 2027 editions.

## Ranking - Best-Masters
Matches: best-masters
Keywords: rankings, ranked, best masters
Best-Masters.com rank, 2026/2027 edition (or undated current ranking) only; from the school or best-masters.com itself.

## Ranking - QS
Matches: \bqs\b|topuniversities
Keywords: rankings, ranked, qs, top universities
QS / TopUniversities rank for this program, 2026/2027 edition only; from the school or topuniversities.com itself.

## Placement
Matches: placement
Keywords: employment report, outcomes, careers, placement, employed
Percentage of graduates employed within the stated window ("92% within 3 months"), 2026/2027 report only.
School's employment report first; otherwise the program's U.S. News or Best-Masters profile (link it).

## Salary
Matches: salary
Keywords: employment report, outcomes, careers, salary
Average (mean) post-graduation base salary, e.g. "$98,000". Median only if labelled ("$95,000 (median)").
School's employment report first; otherwise the program's U.S. News or Best-Masters profile (link it).

## Bonus
Matches: bonus
Keywords: employment report, outcomes, signing bonus
Average signing bonus of graduates, e.g. "$12,500".
