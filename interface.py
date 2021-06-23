import streamlit as lt
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
import altair as alt

lt.set_page_config(
    page_title="EthicsGrade",
)

# CONSTANTS ------------------------------------------------------------------------------------------------------------

DEFAULT_MODEL = "EthicsGrade 6.2"
CURRENT_MODEL = {
    "model_name" : DEFAULT_MODEL
}
DEFAULT_COMPANY_MODEL = "EthicsGrade 6.2"

RATING_ORDER = ['NR', 'R', "D", 'C', 'B', "A", 'A+']
RATING_ORDER_COLOR = ["#000000", "#F36E6E", "#F79C74", "#F5E989", "#82C785", "#60BF85", "#319D46"]


# ----------------------------------------------------------------------------------------------------------------------

class DataHolder:

    def __init__(self):
        self.companies = {}
        self.model_info = None
        self.companies_answers = None
        self.sections = []
        self.sections_weightage = {}
        self.models = {}

    def set_models(self, models):
        for model in models:
            self.models[model.get("model_name")] = model

    def set_companies_data(self, companies_data):
        data = {}
        for company in companies_data:
            company_data = {}
            data[company.get("id")] = company_data
            company_data['name'] = company.get("name")
            company_data['industry'] = company.get("industry")
            answers_data = {}
            company_data['answers'] = answers_data
            for answer in company.get("answers"):
                answers_data[answer.get("question")] = answer
        self.companies_answers = data

    def set_answers(self, answers):
        self.answers = answers

    def set_model_info(self, model_info):
        self.model_info = model_info
        sections = model_info.get("sections")
        self.sections = []
        self.sections_weightage = {}
        for each in sections:
            self.sections.append(each.get("section_name"))
            self.sections_weightage[each.get("section_name")] = each.get("section_weightage")

    def update_sections(self, sections_weightage):
        self.sections_weightage = sections_weightage

    def set_companies(self, companies):
        self.companies = companies

    def add_company(self, company_name, data):
        self.companies[company_name] = data

    def _calculate_rating(self, total_score:int):
        rating = "NR"
        if 50 > total_score > 29:
            rating = "R"
        elif 60 > total_score > 49:
            rating = "D"
        elif 70 > total_score > 59:
            rating = "C"
        elif 80 > total_score > 69:
            rating = "B"
        elif 90 > total_score > 79:
            rating = "A"
        elif total_score >= 90:
            rating = "A+"
        return rating

    def companies_to_pandas(self):
        data = {
            "Company" : [],
            "Industry": []
        }

        for section in self.sections:
            data[section] = []

        data["Total"] = []
        data["Rating"] = []

        for company in self.companies:
            company_data  = self.companies[company]
            total = sum([company_data.get("data")[section] for section in company_data.get("data").keys()])
            total = CalculationEngine.total_score_adjustment(total)
            rating = self._calculate_rating(total)
            data['Company'].append(company)
            data['Industry'].append(company_data.get('industry'))
            data['Total'].append(total)
            data['Rating'].append(rating)
            for section in self.sections:
                data[section].append(company_data.get("data")[section])

        return pd.DataFrame(data)

class DataLoader:
    base_url = "http://ethicdemo-dev.us-west-2.elasticbeanstalk.com"
    urls = {
        "questions" : "apis/model/questions/{}",
        "answers" : "apis/model/answers",
        "models" : "apis/model/models",
        "save_model" : "apis/model/update/{}"
    }

    def __init__(self, data_holder: DataHolder):
        self.holder = data_holder

    def get_models(self):
        data = requests.get(url="{}/{}".format(self.base_url, self.urls['models']))
        self.holder.set_models(data.json())
        return self.holder.models

    def get_model_info(self, model):
        data = requests.get(url="{}/{}".format(self.base_url, self.urls['questions'].format(model.get("model_name"))))
        self.holder.set_model_info(data.json())

    def get_answers(self):
        data = requests.get(url="{}/{}".format(self.base_url, self.urls['answers'])).json()
        self.holder.set_companies_data(data)

    def update_model(self, model, body):
        data = requests.post(url="{}/{}".format(self.base_url, self.urls['save_model'].format(model.get("model_name"))), data=body)
        if data.status_code in [200, 201]:
            lt.sidebar.success("Saved!")


class CalculationEngine:

    def __init__(self, data_holder: DataHolder):
        self.holder = data_holder

    @classmethod
    def group_formula(cls, section_weightage, total_questions_in_group, total_questions_score,
                        group_weightage):
        return round(((total_questions_score*100)*(section_weightage/100)/total_questions_in_group) * (group_weightage/100), 4)

    @classmethod
    def total_score_adjustment(cls, total):
        if 70 > total > 60:
            total = total/ 70*68
        elif 80 > total > 70:
            total = total/ 80*76
        elif 90 > total > 80:
            total = total/90*84
        elif total > 90:
            total = total/ 110*92
        return round(total, 4)

    def calculate_scores_for_companies(self):
        companies = {}
        data = {}
        for section in self.holder.model_info['sections']:
            data[section.get("section_name")] = 0
            section_weightage = self.holder.sections_weightage[section.get("section_name")]
            for company in self.holder.companies_answers:
                company_data = self.holder.companies_answers[company]
                answers = company_data.get("answers")
                industry = company_data.get("industry")
                section_data = 0
                if not company_data.get("name") in companies:
                    companies[company_data.get("name")] = {
                        "data" : {},
                        "industry" : industry
                    }

                for group in section.get("groups"):
                    total_questions_in_group = len(group.get("questions"))
                    total_questions_score = 0
                    for question in group.get("questions"):
                        id = question.get("question_id")
                        answer_data = answers[id]
                        found = answer_data.get("answer_result")
                        if found is not None and found == "YES":
                            total_questions_score += question.get("question_weightage")/100
                    section_data += self.group_formula(
                        section_weightage, total_questions_in_group,
                        total_questions_score, group.get("group_weightage")
                    )
                companies[company_data.get("name")]['data'][section.get("section_name")] = section_data

        self.holder.set_companies(companies)

class VisualisationEngine:

    def __init__(self, data_holder: DataHolder):
        self.holder = data_holder

    def update_data(self, data_holder):
        self.holder = data_holder

    def histogram(self, ds):
        pass



# DATA LOADING PART ----------------------------------------------------------------------------------------------------

data_holder = DataHolder()
data_loader = DataLoader(data_holder)
models = data_loader.get_models()
data_loader.get_model_info(CURRENT_MODEL)
data_loader.get_answers()

# ----------------------------------------------------------------------------------------------------------------------

cal_engine = CalculationEngine(data_holder)

cal_engine.calculate_scores_for_companies()

df = data_holder.companies_to_pandas()

lt.write("""<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.1/dist/js/bootstrap.bundle.min.js" integrity="sha384-gtEjrD/SeCtmISkJkNUaaKMoLD0//ElJ19smozuHV6z3Iehds+3Ulb9Bn9Plx0x4" crossorigin="anonymous"></script>
""", unsafe_allow_html=True)

lt.title("EthiscGrade")

lt.markdown("<hr>", unsafe_allow_html=True)

weightage = data_holder.sections_weightage

sliders = {}

# SIDE BAR -------------------------------------------------------------------------------------------------------------

model_list = list(models.keys())
index = model_list.index(DEFAULT_MODEL)
temp  = model_list[0]
model_list[0] = DEFAULT_MODEL
model_list[index] = temp

CURRENT_MODEL['model_name'] = lt.sidebar.selectbox("Rating View", model_list, index=0)
data_loader.get_model_info(CURRENT_MODEL)
weightage = data_holder.sections_weightage


for section in weightage.keys():
    sliders[section] = lt.sidebar.slider(section, min_value=0.0, max_value=100.0, value=weightage[section])

for section in sliders:
    weightage[section] = float(sliders[section])

if not CURRENT_MODEL['model_name'] == DEFAULT_MODEL:
    if lt.sidebar.button("Save"):
        data_loader.update_model(CURRENT_MODEL, body=data_holder.sections_weightage)

# ----------------------------------------------------------------------------------------------------------------------

data_holder.update_sections(weightage)

cal_engine.calculate_scores_for_companies()

df = data_holder.companies_to_pandas()

df = df.sort_values(['Total'], ascending=False)


# lt.markdown("__Highest Score__ : {}".format(stats['max']))
# lt.markdown("__Lowest Score__ : {}".format(stats['min']))
# lt.markdown("__Average Score__ : {}".format(stats['mean']))
# lt.markdown("__Total Companies__ : {}".format(stats['total_companies']))

col1, col2 = lt.beta_columns(2)

# GROUPING ACCORDING TO RATINGS ----------------------------------------------------------------------------------------

group_data = df.groupby(['Rating'], sort=False)['Company'].count().reset_index()


bar_chart = alt.Chart(group_data).mark_bar().encode(
    alt.X('Rating:O', sort=RATING_ORDER),
    alt.Y("Company:Q", title="Companies"),
    color=alt.Color("Rating", scale=alt.Scale(domain=RATING_ORDER, range=RATING_ORDER_COLOR))
).properties(title="Distribution - Rating")

text = bar_chart.mark_text(
    align="center",
    baseline="middle",
    dy = -5,
    color="black"
).encode(
    text='Company:Q'
)

bar_chart += text

with col1:
    lt.altair_chart(bar_chart, use_container_width=True)

# ----------------------------------------------------------------------------------------------------------------------

# GROUPING ACCORDING TO RATINGS ----------------------------------------------------------------------------------------

group_mean_industry = df.groupby(['Industry'], sort=False)['Total'].mean().reset_index()

bar_chart_industry = alt.Chart(group_mean_industry).mark_bar().encode(
    alt.Y('Industry:O', sort=alt.EncodingSortField(field="Total", order="descending")),
    alt.X("Total:Q", title="Total"),
).properties(title="Distribution - Industry")

text_industry = bar_chart_industry.mark_text(
    align="right",
    baseline="middle",
    dx = -3,
    color="white"
).encode(
    text=alt.Text('Total:Q', format=",.2f")
)

bar_chart_industry += text_industry

with col2:
    lt.altair_chart(bar_chart_industry, use_container_width=True)

# ----------------------------------------------------------------------------------------------------------------------

df = df.reset_index().drop(["index"], axis=1).sort_values(["Industry", "Rating"]).reset_index().drop(['index'], axis=1)
lt.write(df)
if lt.button("Export"):
    df.to_excel("output.xlsx",
                 sheet_name='data')
    lt.success("Downloaded: output.xlsx")
