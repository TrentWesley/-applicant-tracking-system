Project #1: Applicant Tracking System
Question 1 – Django Forms
My ATS uses JobFilterForm and JobOpeningForm, both in jobs/forms.py. JobFilterForm inherits from forms.Form and lets users filter jobs by skill. The filter appears in jobs/templates/jobs/job_list.html. When someone submits it, JobListView in jobs/views.py checks the GET data and filters the jobs shown. It doesn't save anything.

JobOpeningForm inherits from forms.ModelForm and is used to create or edit job openings. The create and edit views in jobs/views.py use it with jobs/templates/jobs/job_form.html to validate the information and save the JobOpening and its selected skills. The main difference is that a regular Form handles input, while a ModelForm is connected to a database model and can save its data.
Question 2 – Many-to-Many Relationship
My JobOpening and Skill models have a many-to-many relationship in jobs/models.py. One job can require multiple skills, and the same skill can be used by multiple jobs, so one foreign key wouldn't work.

I used an explicitly defined association model called JobSkill through ManyToManyField(..., through="JobSkill"), rather than Django's automatic table. It connects a job and a skill using two foreign keys and prevents duplicate job-skill pairs. It doesn't store extra details like skill level. It also protects skills from being deleted while a job still uses them.
Question 3 – Prototype Decision
For my UI prototype, I wanted to figure out which dashboard layout would be easiest to use. I compared a sidebar dashboard, a pipeline board, and an inbox-style layout. The pipeline board looked nice but made dragging between hiring stages seem possible, while the inbox layout hid information behind tabs.

I chose the sidebar dashboard with the clearer status badges from the pipeline design. It keeps the main pages easy to reach and shows statistics, pipeline counts, items needing attention, and recent activity together. This choice is documented in prototypes/dashboard-ui-findings.md and the PRD. You can see it in templates/base.html and core/templates/core/dashboard.html.
Question 4 – Code-Design Decision
One design decision I approved was keeping hiring-stage rules in one service instead of putting separate logic in every view. Putting the rules in each view might have been easier initially, but it could lead to inconsistent checks or missing history records.

The shared change_stage logic is in pipeline/services.py, and pipeline/views.py calls it when users advance, reject, withdraw, or reactivate an application. It checks whether a move is allowed and records successful changes in StageChange. The hiring-stage prototype helped us test things like stale screens and permanent Hired status. I chose this approach because it keeps the hiring process consistent and easier to test.
