Machine Learning (2024) 113:3073–3110
https://doi.org/10.1007/s10994-024-06534-x

Machine learning with a reject option: a survey
Kilian Hendrickx1,2
Jesse Davis5

· Lorenzo Perini2 · Dries Van der Plas2,3,4 · Wannes Meert5 ·

Received: 26 July 2021 / Revised: 16 February 2024 / Accepted: 20 February 2024 /
Published online: 29 March 2024
© The Author(s), under exclusive licence to Springer Science+Business Media LLC, part of Springer Nature 2024

Abstract
Machine learning models always make a prediction, even when it is likely to be inaccurate. This behavior should be avoided in many decision support applications, where mistakes can have severe consequences. Albeit already studied in 1970, machine learning with
rejection recently gained interest. This machine learning subfield enables machine learning
models to abstain from making a prediction when likely to make a mistake. This survey
aims to provide an overview on machine learning with rejection. We introduce the conditions leading to two types of rejection, ambiguity and novelty rejection, which we carefully
formalize. Moreover, we review and categorize strategies to evaluate a model’s predictive
and rejective quality. Additionally, we define the existing architectures for models with
rejection and describe the standard techniques for learning such models. Finally, we provide examples of relevant application domains and show how machine learning with rejection relates to other machine learning research areas.
Keywords Machine learning with rejection · Supervised learning · Trustworthy machine
learning
Mathematics Subject Classification 68T05 · 68T02

1 Introduction
The canonical task in machine learning is to learn a predictive model that captures the
relationship between a set of input variables and a target variable on the basis of training
data. Machine-learned models are powerful because, after training, they offer the ability to
make accurate predictions about future examples. Since this enables automating a number
of tasks that are difficult and/or time-consuming, such models are ubiquitously deployed.
However, their key functionality of always returning a prediction for a given novel
input is also a drawback. While the model may produce accurate predictions in general,
Editor: Johannes Fürnkranz.
Kilian Hendrickx and Lorenzo Perini have contributed equally to this work.
Extended author information available on the last page of the article

13

Vol.:(0123456789)

3074

Machine Learning (2024) 113:3073–3110

in certain circumstances this may not be the case. For instance, there could be certain
regions of the feature space where the model struggles to differentiate among the different classes. Or the current test example could be highly dissimilar to the data used to
train the model. In certain application domains, such as medical diagnostics (Kotropoulos & Arce, 2009) and engineering (Zou et al., 2011), mispredictions can have serious
consequences. Therefore, it would be beneficial for a model to be cautious in situations
where it is uncertain about its predictions. The prediction task could be deferred to a
human expert in these situations.
One way to accomplish this is to use machine learning models with rejection. Such
models assess their confidence in each prediction and have the option to abstain from
making a prediction when they are likely to make a mistake. This ability to abstain from
making a prediction has several benefits. First, by only making predictions when it is
confident, it can result in improved performance for the retained examples (Pudil et al.,
1992). Second, avoiding mispredictions can increase a user’s trust in the system (ElYaniv & Wiener, 2010). Third, it can still result in time savings by only requiring human
interventions to make decisions in a small number of cases. Fourth, avoiding strongly
biased predictions helps build a more fair model (Lee et al., 2021; Ruggieri et al., 2023).
This machine learning sub-field was already studied in 1970 by Chow (1970) and Hellman (1970). However, the proliferation of applications has resulted in renewed interest
in this area.
This survey aims to provide an overview of the subfield of machine learning with
rejection, which we structure around eight key research questions.
Q1. How can we formalize the conditions for which a model should abstain from making
a prediction?
Q2. How can we evaluate the performance of a model with rejection?
Q3. What architectures are possible for operationalizing (i.e., putting this into practice) the
ability to abstain from making a prediction?
Q4. How do we learn models with rejection?
Q5. What are the main pros and cons of using a specific architecture?
Q6. How can we combine multiple rejectors?
Q7. Where does the need for machine learning with rejection methods arise in real-world
applications?
Q8. How does machine learning with rejection relate to other research areas?
In addition to the individual contributions of addressing each of these research questions, our major contribution is that we identify the main characteristics of machine
learning models with rejection, allowing us to structure the methods in this research
field. By providing an overview of the research field as well as deeper insights into the
various techniques, we aid in further advance this research area, as well as its adaptation
to real-world applications.
The remainder of this paper is structured as follows. In Sect. 2, we formalize the
setting in which machine learning with rejection operates and identify the two main
motivations to abstain from making a prediction (Q1). Section 3 introduces the means
to evaluate the performance of models with rejection (Q2). Sections 4, 5, and 6 provide
a structured overview of the actionable techniques to reject based on the relevant literature. In these sections, we focus on describing the architecture (Q3), the rejector’s
learning (Q4), and the key pros and cons (Q5). In Sect. 7 we explore how to combine

13

3075

Machine Learning (2024) 113:3073–3110

multiple rejectors to allow different types of rejection (Q6) Sect. 8 discusses the main
application fields (Q7), while Sect. 9 explores the relation of machine learning with
rejection with other research areas (Q8). Finally, Sect. 10 summarizes our conclusions
and lists the main open research questions.

2 The learning with reject problem setting
In the standard supervised setting, a learner has access to a training set
D = {(x1 , y1 ), … , (xn , yn )}, where each xi is a d dimensional vector and yi is the target. The
training data is assumed to be independent and identically distributed (i.i.d.) according to
some unknown probability measure P (with density p(X, Y)). More generally, we denote
the feature space as X and the target space as Y , which could be discrete Y = {1, 2, … , K},
continuous Y = ℝ, or even probabilistic Y = [0, 1].
The assumption is that there is an unknown, non-deterministic function f ∶ X → Y
that maps the examples to their target value. Given a hypothesis space H of functions
h ∶ X → Y , the goal of a learner is to find a good approximation to f. Typically, this can be
done by finding a model h ∈ H with a small expected risk R which is usually approximated
using the training data

R(h)∶=

∫X×Y

∑ L(h(xi ), yi )
n

L(h(x), y)dP(x, y) ≈

i=1

n

,

(1)

where L is a suitable loss function such as the squared or zero–one loss.

2.1 Models with a reject option
In learning with rejection, the output space of the model is extended to include a new value
R (Cortes et al., 2016a, 2018; Gamelas Sousa et al., 2014a). This new symbol means that
the model abstains from making a prediction. When performing classification with rejection, which is also called cautious classification, this new output R can be seen as an additional class (Ferri & Hernández-Orallo, 2004).
Conceptually, since h only approximates the true underlying model, there are likely
regions of X where h systematically differs from f. Specifically, discrepancies between
h and f can be due to inconsistent data (e.g., classes overlapping), insufficient data (e.g.,
unexplored regions), or even incorrect model assumptions (e.g., h must be linear while f is
not). Therefore, the goal of rejection is to determine such regions in order to abstain from
making likely inaccurate predictions.
Formally, a model with rejection m ∶ X → Y ∪ { R } is represented by a pair (h, r),
where h ∶ X → Y is the predictor and r ∶ R → ℝ is the rejector. Note that the rejector may
use a variety of different inputs such as examples (R = X ), confidence or probability values (R = [0, 1]), or even both (R = X × [0, 1]). At prediction time, m outputs the symbol
R and abstains from making predictions when the rejector r determines that the predictor is at a heightened risk of making a misprediction and otherwise returns the predictor’s
output:
{
R if the prediction is rejected;
m(x) =
(2)
h(x) if the prediction is accepted.

13

3076

Machine Learning (2024) 113:3073–3110

At prediction time, the key design decision for a model with rejection is how to structure
the relationship between the predictor and rejector. Based on our analysis of the literature,
we have identified three common architectural principles.
Separated rejector architecture. The rejector operates independently from the predictor.
The most typical operationalization of this architecture lets the rejector serve as a filter
that decides whether to pass a test example to the predictor. Figure 1 shows the test time
data flow of a separated rejector.
Dependent rejector architecture. Here, the rejector bases its decision on the output of
the predictor. For instance, the dependent rejector can look at how close a prediction
is to the predictor’s decision boundary and abstain if it is too close. Figure 2 shows the
data flow for the dependent rejector.
Integrated rejector architecture. This principle involves integrating the rejector and
predictor into a single model m by treating rejection as an additional class that can be
returned by the model m. Thus, it is impossible to distinguish between the role of the
predictor h and the rejector r. Figure 3 illustrates this scenario.

2.2 Types of rejection
At a high-level, a learned predictor can exhibit (high) uncertainty in its predictions for four
reasons:
R1.	There can be cases where a vector xi ∈ X is associated with multiple values from the
target space Y . This can arise in situations such as when classes overlap in classification tasks.

Fig. 1  Data flow in a separated rejector, in which both the predictor and the rejector are stand-alone models.
The rejector is a filter and only passes accepted examples to the predictor

Fig. 2  Data flow in a dependent rejector. First, the predictor processes the example at hand. Next, the rejector assesses the confidence in the prediction based on the predictor’s representation of the example

Fig. 3  Data flow in an integrated rejector, in which the predictor and rejector are one model. This model
embeds the reject and predict functions and directly outputs a prediction or a rejection

13

Machine Learning (2024) 113:3073–3110

3077

R2.	Some instances in the training data are incorrect (e.g., the values of certain features
were recorded incorrectly, labeling errors).
R3.	
P(X, Y) might differ between the training phase and deployment (e.g., concept drift).
Consequently, the training data is no longer representative.
R4.	Some examples x could simply not be acquired due to their inherent rarity (anomalies, out-of-distribution).
Based on this intuition, two types of rejections can be performed:
Ambiguity Rejection: occurs if x falls in a region where the target y is ambiguous (R1
and R2). This often occurs in regions that are close to the decision boundary in classification tasks;
Novelty Rejection: occurs if x falls in a region where there was little (or no) training
data. Hence, the predictor may struggle to make accurate predictions because it did not
see enough data to accurately model the relationship between X and Y (R3 and R4).

2.2.1 Ambiguity rejection
Ambiguity rejection allows a model to abstain from making a prediction for an example
x in regions where, despite having access to some training examples, the model h fails to
capture the correct relationship f between X and Y (Flores, 1958; Hellman, 1970; Fukunaga
& Kessell, 1972). This can happen for two reasons.
First, the observed relationship between X and Y is not deterministic. This can arise due
to the intrinsic probabilistic nature of Y|X, which a deterministic predictor h cannot handle
(e.g., coin toss), or the training data containing too many errors (e.g., incorrectly labeled
examples), which would make it difficult for h to approximate f. In classification, this can
arise due to classes overlapping in certain regions of the instance-space (Fig. 4a), while in
regression, it leads to high variance in the target variable in certain regions (Fig. 5a). One
way to interpret this issue is that the chosen feature space does not allow for accurately
determining the target value (e.g., missing features might cause examples with different
predictions to be projected onto the same example (Van Craenendonck et al. 2018, Fig. 2)).

Fig. 4  Illustration of a classification scenario where the two classes overlap in a region. The dotted lines
represent the rejector, the dash-dotted line the fitted predictor h, and the solid line the ground truth relation
f. a Shows ambiguity rejection due to a non-deterministic relation between X and Y, b introduces ambiguity
rejection due to the model bias, and c illustrates an example of novelty rejection. While in the first two plots
the rejection region is inside the two dotted lines (examples with cross marks are rejected), in the third figure the rejected novel examples (stars) are outside the dotted line

13

3078

Machine Learning (2024) 113:3073–3110

Fig. 5  Illustration of a regression scenario where rejection can be applied. The dash-dotted line represents
the predictor h, while the solid line indicates the true function f. In a, examples in between the dotted lines
are rejected (cross mark) due to the high variance of Y. In b, examples indicated with the cross mark are
rejected due to the incorrect model bias. In c, star-marked examples are rejected because they differ from
the training data (novelties)

Second, a poor choice of the predictor’s hypothesis space makes it impossible to learn
the relationship between X and Y. This occurs when the chosen hypothesis space H does
not include f. Figure 4b illustrates this error in binary classification, where only linear models (e.g., perceptron) are considered for H while the true target concept f is non-linear.
Similarly, Fig. 5b shows a regression problem with H as the family of quadratic models,
while f is non-quadratic. In both cases, the expected prediction error is large for certain
examples because f ∉ H.

2.2.2 Novelty rejection
Many machine learning models struggle when forced to extrapolate to regions of the feature space that were not (sufficiently) present in the training data (Cordella et al., 1995a;
Sambu Seo et al., 2000; Vailaya & Jain, 2000).
Novelty rejection allows a model to abstain from making predictions for examples that
are sufficiently different from the training data (Dubuisson & Masson, 1993). For such
examples, the predictor h is likely to make mistakes because the absence of training data
similar to x prevents h from learning the correct target y.
In practice, this arises when one of the following assumptions of the training procedure
is violated. First, the sampling distribution differs from the true distribution. Thus, parts of
the feature space are not represented in the data (e.g., the data does not contain any examples of patients suffering from a particular rare disease) (Van der Plas et al., 2021) or one
cannot generate data for all imaginable situations (e.g., a sensor can break in many different ways) (Hendrickx et al., 2022; Urahama & Furukawa, 1995; Hsu et al., 2020). Second,
the skew in the class distribution is too large that the model ignores parts of the feature
space. Thus, the predictor may choose to ignore these examples in its objective to optimize
the accuracy model-complexity trade-off. Third, a new distribution appears after training
and these new examples are out-of-distribution. For instance, this can arise due to drift that
leads to new classes (Landgrebe et al., 2004) or an adversarial agent that deliberately tries
to mislead (Wang & Yiu, 2020; Corbière et al., 2022).
Figures 4c and 5c illustrate this rejection type for a classification and a regression
problem. In both cases, the three black stars represent test examples that are far away
from the training examples. The learned model h may be inaccurate in these regions due

13

Machine Learning (2024) 113:3073–3110

3079

to the lack of training data, which increases the chance of making a misprediction for
these test examples.
The importance of novelty rejection often becomes particularly apparent in medical applications since in many of these applications, it is challenging or expensive to
get an exhaustive training set. Therefore, the training set might only include patients
from specific age groups or with particular medical conditions. For instance, Van der
Plas et al. (2021) learned a sleep stage classifier but only had access to a training set
containing adult patients. Consequently, the model may not perform well when applied
in practice to patients that are different than those encountered during training such as
children or people suffering from extremely rare disorders. However, this information
and the assumptions made during data collection might not be available to the user of
the model. Therefore, adding a novelty rejector is crucial to avoid poor prediction performance on these patients. In this case, a rejector based on a LOF outlier detector can
reject the predictions from children as they have a different morphology than the adults
in the training set (Fig. 6). This mitigates the risk of incorrect predictions.

3 Evaluating models with rejection
Conceptually, a model with a reject option involves evaluating the outputs of both the
predictor and the rejector. Thus, its performance can be viewed through the prism of the
confusion matrix shown in Table 1, where the columns represent the rejector’s decision
and the rows whether the predictor’s output is correct or not. Intuitively, the learning-toreject model is “correct” if a correct prediction is returned to the user (a true accept) or an
example is rejected when the model’s prediction was wrong (a true reject). It is considered
to have made a “mistake” if the model provides the user with an incorrect prediction (false
accept) or rejects an example for which the model’s prediction was correct.
Viewed through this lens, a model with rejection has two goals. On the one hand, it
wants to have high accuracy A on examples for which it makes a prediction:

Fig. 6  Results of a novelty reject option in a sleep stage scoring application (Van der Plas et al., 2021). The
predictor is trained only on adults. The accuracy on children (66.8%) is much lower than the accuracy on
adults (77.7%). Introducing the reject option mitigates the risk of making incorrect predictions as it ends up
rejecting the predictions for most children

13

Machine Learning (2024) 113:3073–3110

3080
Table 1  Confusion matrix
for learning-to-reject models.
The columns show whether an
example is rejected, the rows
show whether h’s prediction is
correct

Prediction

Rejection
No

Yes

Correct

True accept (TA)

False reject (FR)

Incorrect

False accept (FA)

True reject (TR)

A=

TA
.
TA + FA

This makes the model reliable as practitioners can trust its outputs. On the other hand, it
wants to have high coverage:

𝜙=

TA + FA
.
TA + FA + FR + TR

That is, it should make a prediction for as many test examples as possible (De Stefano
et al., 2000; El-Yaniv & Wiener, 2010; Lei, 2014). This can alternatively be viewed as
having a low rejection rate, defined as 1 − 𝜙. This makes the model useful in practice as its
predictions can be utilized for decision-making. Unfortunately, these two goals are competing as the accuracy can be increased by limiting the predictions to the most confident cases,
i.e., reducing the coverage (Hansen et al., 1997; Homenda et al., 2016). As a result, metrics
specifically tailored to learning to reject must capture this trade-off (Cordelia et al., 1998).
Broadly speaking, three categories of metrics exist that evaluate different aspects of a
model with rejection:
Evaluating models for a given rejection rate: This entails having a fixed rejection rate
provided by the user. In this case, one only needs to evaluate performance on the nonrejected examples and it is possible to use the standard evaluations (e.g., accuracy (Golfarelli et al., 1997));
Evaluating the overall model performance/rejection trade-off: One can plot the rejection
rate on the x-axis and the predictor’s performance obtained on a representative test set
on the y-axis, similar to Receiver Operating Characteristic (ROC) analysis;
Evaluating models through a cost function: This case only requires knowing the model’s
output and the costs for (mis)predictions and rejections.

3.1 Evaluating models with a fixed rejection rate
Given a dataset and a fixed rejection rate, Condessa et al. (2017) argue that a good evaluation metric should meet four main criteria: given a fixed predictor, such metric should: (p1)
depend on the model’s rejection rate; (p2) be able to compare two models with different
rejectors for a given rejection rate (and for the same predictor); (p3) be able to compare two
models with different rejectors with different rejection rates when one clearly outperforms
the other; (p4) reach its maximum value for a perfect rejector (i.e., a rejector that rejects all
misclassified examples) and its minimum value for a rejector that rejects all accurate predictions. In addition, Condessa et al. (2017) propose three types of evaluation metrics that
meet the required conditions:

13

3081

Machine Learning (2024) 113:3073–3110

(a)	
Prediction quality. The model’s prediction quality (PQ) measures the predictor’s performance on the non-rejected examples. For instance, one can use classical evaluation metrics on the accepted examples such as the accuracy

PQACC =

TA
,
TA + FA

the F-scores (Pillai et al., 2011; Mesquita et al., 2016) or any other evaluation metric,
including fairness metrics (Madras et al., 2018). While this allows comparing models with
different rejectors, looking only at the prediction quality will tend to favor the model with
the highest rejection rate. By being more conservative (i.e., having a lower coverage),
the model tends only to offer predictions for the subset of examples for which it is most
confident.
(b)	
Rejection quality. The rejection quality (RQ) indicates the rejector’s ability to reject
misclassified examples. One way to do this is by comparing the ratio of misclassified
FA+TR
TR
) to the ratio on the complete dataset ( TA+FR
), i.e.
examples on the rejected subset ( FR
/
TR FA + TR
RQRATIO =
.
FR TA + FR
Looking only at the rejection quality will favor models with the lowest rejection rate. The
lower the rejection rate is, the more likely the rejector is to abstain only on those few examples for which it is most confident that the predictor will make a mistake.
(c)	
Combined quality. The combined quality (CQ) evaluates the model with a reject
option as a whole. One way to accomplish this is by combining the predictor’s performance on the non-rejected examples (prediction quality) with the rejector’s performance on the misclassified examples (rejection quality). For instance, using PQACC
and RQRATIO yields to
TA + TR
CQACC-RATIO =
.
TA + FA + FR + TR
Overall, the combined quality offers a more holistic assessment of the model’s overall
performance as it measures both the predictor’s and the rejector’s quality (Lin et al., 2018).
The downside is that aggregating the two metrics yields a less fine-grained characterization
of the model performance. Specifically, in case a model has low CQ, it is hard to ascertain
which component, the predictor or rejector, is contributing the most to the model’s poor
performance.
Pros and Cons. The main advantage of this category is that the metrics clearly measure
the fine-grained model performance in the given setting. However, using one of these types
of metrics may be limiting in some cases. For instance, theoretical research may not care
about evaluating the model with rejection for a specific rejection rate, as it is usually specified based on domain knowledge. Moreover, given a rejection rate, not all performance
metrics can be always used, as some may suffer from task-related issues. For instance,
rejecting a whole class would not allow utilizing metrics like F1-score and AUC for the
prediction quality as they need both classes’ labels.

3.2 Evaluating the model performance/rejection trade‑off
To assess the performance-rejection trade-off, a common approach is to evaluate the prediction quality (for non-rejected examples) by varying the rejection rate from 0% to 100%,

13

3082

Machine Learning (2024) 113:3073–3110

which is known as the Accuracy-Reject Curve (ARC) (Nadeem et al., 2010). This involves
plotting the rejection rate on the x-axis and the prediction quality (e.g., accuracy) on the
y-axis (Hanczar & Sebag, 2014). Higher curves indicate better performance. Alternatively,
risk-based metrics like mean squared error can be plotted, with lower curves indicating better performance (Sambu Seo et al., 2000). Sometimes the predictor’s performance on the
rejected examples is also shown with the intuition that it should be worse on this subset of
the data than on the accepted ones (Zou et al., 2011; Condessa et al., 2015c, b).
When comparing two models using the ARC method, two scenarios arise. First, one
model clearly outperforms the other in terms of prediction quality for all rejection rates.
Second, the models show varying prediction quality across different rejection rates. To
illustrate this, consider Fig. 7 where the light blue curve only outperforms the black curves
if the rejection rate is lower than 0.01. When it is not clear which model performs best, the
overall performance can be assessed using the Area Under the ARC Curve (AURC), similar to the AUC in standard machine learning (Vanderlooy et al., 2006a, b; Landgrebe et al.,
2006). In this example, the AURC of the light blue curve will be higher than the AURC of
the black curves, indicating that it performs better overall than the black curves.
Pros and Cons. The main advantage of this category is that any prediction quality metric can be used on the y-axis. Moreover, they provide a high-level overview of how the
model works for different rejection rates. However, generating these curves can be challenging for two reasons. First, some rejectors do not allow directly setting the rejection
rate (Wu et al., 2007; Homenda et al., 2014), but they might have other hyperparameters
(e.g., rejection threshold). Mapping these to rejection rates may be challenging and may
not be possible to achieve all possible rejection rates. Second, altering the rejection rate of
a model with rejection can require completely retraining the whole model. This may be too
computationally demanding to perform a fine-grained analysis (Condessa et al., 2017).

3.3 Evaluating models through a cost function
For classification tasks, one can ask the user to specify the costs for (mis)predictions as
well as for rejection and evaluate a model by its (expected) total cost at test time. Although
the costs can be designed as a continuous function of the examples (Mozannar & Sontag,
2020; De et al., 2021), the cost function typically accounts only for three constant costs: the

Fig. 7  Example of an accuracy-reject curve in which Van der Plas et al. (2023) compare two of their proposed models with a novelty reject option (blue) with two models that were used as baseline (black). The
proposed models outperform the baselines but the light blue model only does for rejection rates lower than
0.01

13

Machine Learning (2024) 113:3073–3110

3083

cost of correct prediction Cc, the cost of a prediction error Ce, and the cost of rejection Cr
such that Cc < Cr < Ce (De Stefano et al., 2000; Balsubramani, 2016; Condessa et al.,
2013). Without loss of generality, usually one assumes normalized costs, i.e., Cc = 0,
Ce = 1 and Cr ∈ [0, 1] in which the normalized value for Cr can be obtained from the initial
C −C
values as Cr −Cc . Although the costs need to be set based on some domain knowledge, there
e

c

are two constraints for setting the rejection cost properly. First, it must be lower than a random predictor’s average cost for a classification task with K classes, i.e. Cr ≤ K1 (Cordella
et al., 1995b; Herbei & Wegkamp, 2006). Otherwise, the expected cost of always making a
random prediction would be lower than the rejection cost, which nullifies the task of rejection. Second, one should account for possible imbalance classes by setting
Cr ≤ 1 − maxk≤K P(Y = k), where P(Y = k) is the class frequency (Perini et al., 2023). In
fact, for higher Cr , a naive model that always predicts the most frequent class k̄ would
obtain a cost equal to 1 − P(Y = ̄k) and rejecting examples would not be worth it for higher
rejection costs.
Pros and Cons. The main benefit of this category is its high interpretability: given a final
cost, we can easily go back to the causes that yield such a cost. Moreover, one can use the
same cost function to optimize the model parameters during the learning phase. This ensures
coherence between learning the optimal model at training time and measuring its performance at test time. However, this category has the key drawback that the user must set the
cost function based on domain knowledge, which is not always easy to obtain. Setting different costs changes the quality of the models, which may end up ranking several compared
models differently. A way to alleviate this would be to make the Cost-Reject plot (Hanczar,
2019), where, similar to the ARC, the x-axis and y-axis represent respectively the normalized
rejection cost and the normalized prediction cost (Friedel et al., 2006; Abbas et al., 2019).

4 Separated rejector
Separated rejectors operate by filtering out unlikely examples. They are typically used
for novelty rejection though there are some examples of using them for ambiguity rejection (Asif & Minhas, 2020). Because the rejector does not use the predictor’s output in any
way, it is typically a function of the examples: r ∶ X → ℝ. Formally, the separated architecture yields the following model:
{
R if r(x) < 𝜏
m(x) =
(3)
h(x) otherwise.
If the rejector r outputs a value less than 𝜏 , then the model m rejects the example ( R ).
Otherwise, m uses the predictor h to make a prediction.
The separation between predictor and rejector means that the rejector is learned independently of the predictor. The learning task involves learning the rejector itself as well as
setting the threshold 𝜏 . To align with its goal of identifying unlikely or unexpected examples, a common choice is to use anomaly/outlier, out-of-distribution, or novelty detection
algorithms. Three categories of methods can be used for this goal: models that 1) estimate
p(X), 2) are one-class classifiers, and 3) quantify the degree of novelty using a data-driven
score function.
Learning a separated rejector. A first option to learn a separated rejector is to use a
probabilistic model that estimates the marginal density p(X) and to reject a test example x if

13

3084

Machine Learning (2024) 113:3073–3110

p(x) < 𝜏 . These probabilistic models often make assumptions about the distribution of the
examples and are trained to maximize the likelihood of the training dataset (Vasconcelos
et al., 1993). For instance, Landgrebe et al. (2004) proposes a locally normal distribution
assumption and uses a Gaussian Mixture Model (GMM) to estimate p(X) with a specified
number of components whereas others have considered Variational Autoencoders (Wang &
Yiu, 2020) and Normalizing Flows (Nalisnick et al., 2019).
Another option to learn a separated rejector is by employing a one-class classification
model. Generally, they enclose the dataset into a specific surface and flag any example
that falls outside such region as novelty. For instance, a typical approach is to use a OneClass Support Vector Machine (OCSVM) to encapsulate the training data through a hypersphere (Coenen et al., 2020; Homenda et al., 2014). By adjusting the size of the hypersphere, the proportion of non-rejected examples can be increased (Wu et al., 2007).
Alternatively, some models assign scores that represent the degree of novelty of each
example (i.e., the higher the more novel), such as LOF (Van der Plas et al., 2023) or Neural
Networks (Hsu et al., 2020). When dealing with these methods, one often initially transforms the scores into novelty probabilities using heuristic functions, such as sigmoid and
squashing (Vercruyssen et al., 2018), or Gaussian Processes (Martens et al., 2023). Then,
the rejection threshold can be set to reject examples with high novelty probability.
Learning the rejection threshold 𝜏 . The rejection threshold 𝜏 is a crucial parameter
that determines whether an example is rejected or not. In many cases, the threshold is set
based on domain knowledge. For instance, one can introduce adversarial examples and set
a threshold to reject them all (Hosseini et al., 2017). In case the number of novelties is
unknown, one can use existing methods to estimate the contamination factor, i.e. the proportion of novelties, and set the threshold accordingly (Perini et al., 2022b, a). Otherwise,
heuristics can be employed, such as rejecting examples falling within the first or second
percentiles of correctly classified training examples (Wang & Yiu, 2020).
Benefits and drawbacks of a separated rejector. Using a separated rejector has several
benefits. First, the rejector is predictor agnostic. Hence, it can be combined with any type
of predictor. Second, because the rejector can be trained independently of the predictor,
it is possible to augment an existing predictor with a reject option using this architecture.
Third, by serving as a filter, the predictor makes fewer predictions. This is particularly
advantageous when there is a high computational cost associated with using the predictor.
Finally, this architecture is generally simpler to operationalize compared to rejectors that
interact with the predictor. However, there are two evident drawbacks. First, not sharing
information between the predictor and the rejector results often in sub-optimal rejection
performance (Homenda et al., 2014). Second, this architecture is typically only used for
novelty rejection because it is naturally related to assessing whether x is rare or not while
ambiguity rejection requires information on p(Y|X), which is often estimated through the
predictor’s output.

5 Dependent rejector
Dependent rejectors analyze the predictor’s output to identify examples that the predictor is likely to mispredict. The rejector is typically represented as a confidence function
ch ∶ X → [0, 1] that measures how likely the predictor is to make a correct prediction. Formally, the model for a dependent architecture has the form:

13

3085

Machine Learning (2024) 113:3073–3110

{
m(x) =

R if r(x;h) < 𝜏;
h(x) otherwise.

(4)

where r may depend on the feature vector x, and on the predictor h through the confidence
function ch. Similar to the separated rejector, the model rejects the example ( R ) only if the
rejector outputs a value lower than 𝜏 . Without loss of generality, we assume the confidence
values ch (x) ∈ [0, 1], as one can always transform a score function into this range.
The learning task for a dependent rejector usually entails (1) selecting a confidence
function that measures how confident the predictor is in its predictions, and (2) setting
the rejection threshold 𝜏 .
Learning a dependent rejector: types of confidence function ch . The form of the confidence function depends on the desired rejection type. For ambiguity rejection, the metric should indicate the variability of the target variable or the potential predictor bias.
For novelty rejection, the confidence should capture the example’s similarity to the training data. We distinguish among four ways to derive the confidence scores: i) estimating
the conditional probability P(Y|X), ii) estimating the class conditional density p(X|Y),
iii) performing a sensitivity analysis, and iv) exploiting the predictor’s properties.
The conditional probability approaches allow for ambiguity rejections by using the
maximum of the class conditional probability as confidence function (Pazzani et al.,
1994; Fumera et al., 2004; Lam & Suen, 1995)

ch (x) = max P(Y = k|X = x)
k∈Y

(5)

where k is either the true target value or the predictor’s output. Low P(Y|X) values for two
or more targets k1 , k2 ∈ Y indicate high randomness of the data or proximity to the decision boundary (Arlandis et al., 2002). Deriving the conditional probabilities from the predictor’s outputs can be done by post-processing the predictor’s output using techniques
such as sigmoid calibration for binary classification tasks (Cordella et al., 2014; Brinkrolf
& Hammer, 2017)

P(Y = 1|X = x) ≈

1
,
1 + exp(Ah(x) + B)

with parameters A and B learned during the training (Brinkrolf & Hammer, 2018), softmax
transformation for multi-class classification tasks (Kwok, 1999)

exp (hk (x))
,
j∈Y exp (hj (x))

P(Y = k�X = x) ≈ ∑

where hj (x) is the predictor’s output for x related to class j, or by fitting Gaussian Processes
for regression tasks (Sambu Seo et al., 2000). In case of multiple predictors h1 , … , hV ,
one can also measure the ensemble agreement as the conditional probability (Glodek et al.,
2012; Zhang, 2013)
∑V
1[hv (x) = k]
.
P(Y = k�X = x) ≈ v=1
V
On the other hand, the class conditional density approaches perform novelty rejection putting (Dubuisson & Masson, 1993; Dübuisson et al., 1985)

13

Machine Learning (2024) 113:3073–3110

3086

ch (x) = max p(X = x|Y = k).
k∈Y

(6)

Intuitively, a low density p(X|Y) expresses that a sample is rare (Condessa et al., 2015b).
Common methods to estimate the confidence in Eq. 6 employ generative predictors that
directly measure the data density such as Gaussian Mixture Models (GMMs) (Vailaya &
Jain, 2000). It is also possible to employ heuristic approaches such as normalizing the
class distance between the example x and its v−th nearest neighbor x′ (Conte et al., 2012;
Villmann et al., 2015; Fischer et al., 2014b), i.e.

p(X = x�Y = k) ≈ ∑

d(x, x� )

�
{(x∗ ,y∗ )∈D∶y∗ =k} d(x∗ , x∗ )

and computing the proportion of neighbors within a specified radius R (Berlemont et al.,
2015) as

�{x� ∶ d(x, x� ) ≤ R, (x� , y� ) ∈ D, y� = k}�
.
�
(x� ,y� )∈D �{x∗ ∶ d(x , x∗ ) ≤ R, (x∗ , y∗ ) ∈ D, y∗ = k}�

p(X = x�Y = k) ≈ ∑

The sensitivity analysis line allows only ambiguity rejection, as it measures the robustness
of the predictor under perturbation of either (a) its parameters or (b) the examples (Lewicke
et al., 2008; Hellman, 1970). Intuitively, slightly perturbing the predictor’s parameters has
major effects on the predictions only for examples that fall in the proximity of the decision
boundary: slight variations of the parameters yield slight changes in the decision boundary, which, in turn, may end up flipping the predictions for some examples. Examples of
employed perturbations involve adding some noise to the model’s parameter values (e.g.,
adding a random sample from a normal distribution with null mean and small variance to
the weights of a neural network), employing neural networks with a dropout layer (Geifman & El-Yaniv, 2017), or using a Bayesian simulation (Perini et al., 2020b). In the case of
constructing multiple predictors, a common and simple confidence metric is

c{h1 ,…,hM } (x) = 1 − Var{h1 (x), … , hM (x)}
where h1 , … , hM are the M predictors constructed by perturbing the parameters, and the
variance is scaled to be in [0, 1]. In some cases, one can directly employ an ensemble of
M similar predictors and measure the variance of their predictions (Fumera & Roli, 2004;
Jiang et al., 2020).
Alternatively, one can perturb the test example x to be x + 𝜀, where 𝜀 is a random noise
such that ‖𝜀‖ is small. Intuitively, we want a predictor’s output to remain the same when the
example is only slightly perturbed. Thus, the confidence metric should reflect the robustness of h (Mena et al., 2020; Denis & Hebiri, 2020; Kühne et al., 2021), such as

ch (x) = P(h(x + 𝜀) = h(x)),
which measures how likely it is that the prediction does not change when the example is
perturbed. More generally, we can apply transformations such as rotations and symmetries
to the examples (Chen et al., 2018). Finally, because choosing a specific value for 𝜀 is hard,
one can use existing approaches to find each example’s minimum 𝜀 that will alter its predicted label (Devos et al., 2021) and derive a confidence metric as a function of the training
𝜀.

13

3087

Machine Learning (2024) 113:3073–3110

The property-based methods consist of learning the confidence based on some of the
predictor’s properties, such as using the leaf configurations of a tree ensemble or the neural
network’s weight of specific neurons. This line allows both ambiguity and novelty rejection, depending on the utilized property. These methods tend to exploit heuristic and datadriven intuitions and there are no overarching themes that connect these intuitions. For
instance, Devos et al. (2023) present a method to detect evasion attacks in tree ensembles.
By enumerating the leaves of each tree as oi , they map each example x to the configuration
o = (o1 , … , oV ) ∈ ℕV of the V activated leaves (one per tree) when passing x as input to the
ensemble. In such output configuration space, they quantify the proximity to the decision
boundary by measuring the Hamming distance between the configuration o of a test example with ensemble’s prediction y and the closest training example’s configuration o′ with
flipped prediction ̂y ≠ y:
( V
)
∑ [
]
OC-SCORE(x) = min
1 ov ≠ o�v
�
o ∈R ̂y

v=1

where R ̂y is the set of training configurations with flipped predictions. One can derive a
confidence metric ch by, for instance, min-max normalizing the OC-SCORE . On the other
hand, confidence values can also be derived from the weight vectors of a Self-Organizing
Map (SOM) (Gamelas Sousa et al., 2014b, 2015). Because SOM’s can approximate the
input data density, they approximate p(X = x|Y = k) with p(w|Y = k, X = x), where w are
the weights of the neural network, using standard statistical techniques, such as the Parzen
Windows (Alhoniemi et al., 1999). Moreover, El-Yaniv and Wiener (2011) propose a disbelief principle, which computes the confidence function by measuring how much the predictor h deteriorates if retrained with the constraint to predict a specific example x differently (i.e., hx)

ch (x) =

1
,
R(hx ) − R(h)

where R(hx ) > R(h) > 0. Finally, the literature presents additional ad-hoc confidence metrics for k-NN and Random Forest (Göpfert et al., 2018; Dalitz, 2009).
Learning the rejection threshold 𝜏 . Setting an appropriate rejection threshold 𝜏 is crucial
for having an accurate dependent rejector. At a high level, the threshold is set in three main
ways: using domain knowledge, adhering to user-provided constraints, or tuning it empirically based on some objective function.
In some situations, users possess domain knowledge that enables setting 𝜏 to achieve a
desired rejection rate 𝜌 (Le Capitaine & Frélicot, 2012; Pang et al., 2021). Setting 𝜏 in this
situation entails (1) ranking training examples based on their confidence level, and (2) setting 𝜏 such that the desired percentage of predictions are rejected (Sotgiu et al., 2020), that
is, at

PX (ch (x) < 𝜏) = 𝜌.
Note that this approach is also used when evaluating the model performance/rejection
trade-off, which needs to measure the model performance for a fixed rejection rate (see
Sec. 3.2) (Ma et al., 2001; Heo et al., 2018; Fumera et al., 2003).
In other cases, users provide knowledge as specific constraints that should be satisfied (Pietraszek, 2005). On the one hand, the user may provide an upper bound ℜ for
the rejection rate and aim to limit the number of rejections. This results in learning the

13

Machine Learning (2024) 113:3073–3110

3088

appropriate 𝜏 by minimizing the model misclassification risk while adhering to the rejection rate constraint (Zhou et al., 2022; Pugnana & Ruggieri, 2022, 2023)

𝜏 = arg min PXY (h(x) ≠ y, ch (x) ≥ t)

subject to

t∈[0,1]

PX (ch (x) < t) ≤ ℜ.

On the other hand, the user may provide an upper bound 𝔐 for the proportion of mispredictions, and aim to control the allowable error (Varshney, 2011; Sayedi et al., 2010). Thus,
one needs to learn 𝜏 by setting up the complementary problem as before, namely by minimizing the model rejection rate while satisfying the constraints on error (Li & Sethi, 2006;
Franc & Prusa, 2019; Franc et al., 2021)

𝜏 = arg min PX (ch (x) < t)
t∈[0,1]

subject to

PXY (h(x) ≠ y, ch (x) ≥ t) ≤ 𝔐.

Moreover, one can generalize this problem by finding the threshold 𝜏 such that the predictor’s misclassification risk at test time is guaranteed to be bounded with high probability (Geifman & El-Yaniv, 2017).
Finally, it is possible to set 𝜏 empirically according to some objective function. The
most common approach is to set a single global threshold 𝜏 , which makes the rejection
both simple and transparent, yet usually effective (Fukunaga & Kessell, 1972). This is the
case for Chow’s rule (Chow, 1970) which involves learning the optimal 𝜏 by minimizing
the risk function that includes the expected error rate and the rejection rate

⎤
⎡
⎥
⎢
⎥
⎢
p(x) dx⎥.
(1 − ch (x)) p(x) dx + t
𝜏 = arg min ⎢
�
�
t∈[0,1] ⎢ {x∈X∶ch (x)≥t}
{x∈X∶ch (x)<t}
⎥
⎢������������������������������������������� �������������������������⎥
⎦
⎣
R EJECTION RATE
E RROR RATE

(7)

However, in real-world scenarios, obtaining complete knowledge of class distributions is
challenging, limiting the applicability of Chow’s rule (Shekhar et al., 2019). Thus, in a
binary classification case, Tortorella (2000) proposes to use two rejection thresholds 𝜏1 and
𝜏2 such that

⎧ 0 if c (x) < 𝜏 ;
h
1
⎪
h(x) = ⎨ 1 if ch (x) > 𝜏2 ;
⎪ R if 𝜏1 ≤ ch (x) ≤ 𝜏2
⎩

(8)

with ch (x) = P(Y = 1|X = x). He proposes to learn 𝜏1, 𝜏2 by optimizing a cost function that
is identical to finding the intersection between the cost function and the convex hull of the
ROC curve

𝜏1 = arg min P(Y = 1)(Cfn − Cr )FNR(t) + P(Y = 0)(Ctn − Cr )TNR(t)

(9)

𝜏2 = arg min P(Y = 1)(Ctp − Cr )TPR(t) + P(Y = 0)(Cfp − Cr )FPR(t)

(10)

t∈[0,1]

t∈[0,1]

where Cfn, Cfp, Ctn, and Ctp are the costs for false negatives, false positives, true negatives,
and true positives, while FNR(t), TNR(t), TPR(t) and FPR(t) are the false negative, false
positive, true negative and true positive rates obtained by evaluating the models with the

13

3089

Machine Learning (2024) 113:3073–3110

thresholds set to t. This approach is theoretically equivalent to Chow’s rule under the
Bayesian optimality assumption (Santos-Pereira & Pires, 2005; Du et al., 2010). However, when estimating posterior probabilities, Chow’s rule is not suitable, and 𝜏 should be
learned using a cost-based approach (Marrocco et al., 2007; Kotropoulos & Arce, 2009).
Different approaches have extended Tortorella ’s method to address other scenarios (Sansone et al., 2001), such as stable formulations of ROC curves for small datasets (Jigang
et al., 2006), robust and fast-to-retrain rejections for cost-sensitive situations (Dubos et al.,
2016; Fischer et al., 2015b), and tailored solutions for learning meta-classifiers or handling
multiple classes (Pietraszek, 2007; Cecotti & Vajda, 2013).
For tasks requiring a more fine-grained rejection capability, considering multiple
local thresholds 𝜏1 , 𝜏2 , … (up to a finite number) may be beneficial (Muzzolini et al.,
1998; Kummert et al., 2016; Krawczyk & Cano, 2018). Normally, setting local thresholds requires dividing the feature space into J regions Ji and setting a (local) threshold
in each region. For instance, one can design regions and thresholds by
• constructing one region for each class, i.e. Ji = {x∗ | y∗ = i}, which means that the
number of regions J equals the number of classes K (Fumera et al., 2000); then, one
often finds the local threshold by using for each Ji the same approach as for global
thresholds;
• using the Voronoi-cell decomposition, which requires J prototypes wi to have
Ji = {x∗ | d(x∗ , wj ) ≤ d(x∗ , wk ) ∀k ≠ i}, for i ≤ J (Villmann et al., 2015; Fischer
et al., 2015a, b; Fischer & Villmann, 2016); then, Fischer et al. (2014a) present a
greedy optimization method to adaptively determine local thresholds using a heuristic principle;
• setting up an optimization problem that finds the optimal thresholds by assigning
different class rejection costs; for instance, in binary classification, Zheng et al.
(2011) proposes to find
[
𝜏1 , 𝜏2 = arg min PXY (ch (x) < t1 |y = 0)Cr,0 + PXY (ch (x) < t2 |y = 1)Cr,1
0≤t1 ,t2 ≤1

+ PXY (m(x) ≠ y)Ce

]

where Cr,0 and Cr,1 are the costs for rejecting examples from the negative and positive
classes;
• optimizing an objective function that accounts for different user-specified class misclassification risks 𝔐1 , … , 𝔐K ; Lin et al. (2022) treat each class independently, setting

L(tk ) = ̂A(tk ) +

K
∑

𝜆j ( ̂
𝔐j − 𝔐j )2

j

where ̂A(tk ) is any ambiguity metric, 𝜆j is a penalization term that needs to be set to
̂
high values to penalize high differences between the model’s misclassification risk 𝔐
and the user-specified target.
Although multiple thresholds give more fine-grained control over a rejector’s performance (Laroui et al., 2021; Gangrade et al., 2021a), this is usually more computationally
expensive. However, Fischer et al. (2016) propose efficient schemes for optimizing local
thresholds and show that the computation time can be reduced to polynomial (Boulegane et al., 2019).

13

Machine Learning (2024) 113:3073–3110

3090

Benefits and drawbacks of a dependent rejector. Designing a dependent rejector has several benefits. First, the interaction between the predictor and rejector enables both types of
rejection, because the rejector learns from the predictor’s output the regions of the feature
space where examples are mispredicted or unlikely to fall. Second, a dependent rejector
can extend an existing predictor (including black-box) by simply setting a proper threshold
on a confidence measure. Third, it allows the reuse of previously learned models, eliminating the need for costly retraining (Zou et al., 2011; Tang & Sazonov, 2014). Fourth,
a confidence-based rejection could be improved by considering multiple confidence metrics where each one captures different aspects of the underlying uncertainty (Tax & Duin,
2008). However, this architecture has potential drawbacks as well. First, the quality of the
dependent rejector is highly influenced by the quality of the confidence metric, which is
usually hard to evaluate. Second, typically a dependent rejector does not affect the predictor’s learning phase. This results in possible sub-optimal predictions of the model with a
reject option.

6 Integrated rejector
The integrated rejector combines the rejector and predictor into a single model where it
is impossible to distinguish between the role of the h and the r. Formally, the model with
integrated reject option acts as

m(x) ∈ Y ∪ { R }.

(11)

Conceptually, this model simply includes R as an additional output.
This architecture usually needs a unique algorithm for learning predictor and rejector in tandem (Cortes et al., 2016a, b). There are two distinct approaches to learning an
integrated rejector. The first approach is model-agnostic and involves designing an objective function that penalizes (mis)predictions as well as rejections. The second approach is
model-specific and entails integrating a rejector into an existing predictor, where rejection
becomes part of the decision-making process.
Learning a model-agnostic integrated rejector. Typically, learning a model that simultaneously makes accurate predictions and rejects the examples that will be otherwise mispredicted can be done by simply designing a specialized objective function (Mozannar &
Sontag, 2020). Then, such a function can be minimized using potentially any existing optimizer, which makes it model-agnostic. For instance, for classification, a simple cost-based
objective for any hypothesis m can be expressed as
[
]
(x) + 1
L = 𝔼p(X,Y) Cr 1
(x)
m(x)= R
m(x)∉{y, R }
with Cr ∈ (0, 1∕2]. For tasks other than classification, ad-hoc loss functions are used, such
as those for multilabel classification (Pillai et al., 2013; Nguyen & Hüllermeier, 2020,
2021), regression (Asif & Minhas, 2020; Kalai & Kanade, 2021), online learning (Cortes
et al., 2018; Kocak et al., 2020), and multi-instance learning (Zhang & Metaxas, 2006).
However, in many cases, surrogate losses are employed to enable efficient optimization, as
learning from discrete losses is computationally impractical (Wegkamp, 2007; Grandvalet
et al., 2009; Cao et al., 2022). Consequently, the original loss L is converted into a convex loss by utilizing surrogate functions 𝜓 ∶ ℝ → ℝ, such as the logistic and hinge functions (Ramaswamy et al., 2018; Zhang et al., 2018; Bartlett & Wegkamp, 2008):

13

3091

Machine Learning (2024) 113:3073–3110

1
,
Logistic: 𝜓(L) =
1 + exp(L)

⎧ 1 − 1−Cr L if L < 0
Cr
⎪
Hinge: 𝜓(L) = ⎨ 1 − L
if 0 ≤ L < 1
⎪0
otherwise
⎩

For the hinge loss to be convex, it is required that Cr ≤ 1∕2 which is the case for classification as otherwise the cost of rejection would be higher than the cost of random guessing. Numerous studies in the literature have explored the properties of surrogate loss
functions (Yuan & Wegkamp, 2010), including calibration effects (Ni et al., 2019; Charoenphakdee et al., 2021), estimates of bounds for misclassification risk (Shekhar et al.,
2019; Kato et al., 2020), penalization effects in high-dimensional spaces (Wegkamp &
Yuan, 2012), proximity to the optimal Bayes solution (Bounsiar et al., 2008; Shen et al.,
2020a), and convergence rate analysis (Denis & Hebiri, 2020).
Lastly, one can allocate an extra class K + 1 (commonly known as the reject class) for
rejection and assign a specific penalization cost Cr for predicting such a class. With this setting, there are two main alternatives. In the first case, there are no actual examples belonging to this class. Thus, these approaches design loss functions to enable the classifier to
assign on its own a positive score to ambiguous examples (Huang et al., 2020; Feng et al.,
2022). For instance, Ziyin et al. (2019) propose to measure the expected loss as
[
]
1
L = 𝔼p(X,Y) log(sk (x) + sK+1 (x)) ,
Cr
where sk (x) and sK+1 (x) are probabilities, respectively, for the class y = k and K + 1 (rejection). At a high level, decreasing the rejection cost Cr results in higher chances of rejection. In the second case, one artificially generates examples xn+1 , … , xN (e.g., adversarial
examples) and assigns them to the rejection class K + 1. By training a predictor with K + 1
classes, the reject option is naturally incorporated as output, and any (multi-class) predictor can be used for novelty (Vasconcelos et al., 1995; Singh & Markou, 2004; Urahama &
Furukawa, 1995) or ambiguity rejection (Thulasidasan et al., 2019; Pang et al., 2022).
Learning a model-specific integrated rejector. In many practical use cases, one may
already know that a specific class of models works well within the given context, such as
SVM models in medical applications (Hanczar & Dougherty, 2008; Hamid et al., 2017).
Given a specific predictor, its learning algorithm can be slightly adapted to include
the reject option. For instance, integrated SVMs set two (or more) hyperplanes on the
feature space and reject all the examples located in between them (Pillai et al., 2011;
Lin et al., 2018; Zidelmal et al., 2012). Figure 8 shows two common cases to learn the
hyperplanes. First, one can parametrize the hyperplane as w ⋅ x + b ± 𝜀 = 0 , with 𝜀 ≥ 0 ,

Fig. 8  Two cases of Integrated SVMs: a on the left side, the two hyperplanes are parallel and equidistant
to the decision boundary (dashed line), b on the right side, each SVM gives higher priority to one class by
limiting mispredictions

13

Machine Learning (2024) 113:3073–3110

3092

which results in parallel and equidistant hyperplanes from the decision boundary, where
𝜀 indicates the distance (Fumera & Roli, 2002). Learning such hyperplanes requires
minimizing the empirical loss

L=

n
n
∑
∑
[
]
1
w⋅w+C
l(𝜉i , 𝜀) −
𝛼i yi (w ⋅ xi + b) − 1 + 𝜉i
2
i=1
i=1

where w is the weight vector, b is the intercept of the hyperplane, C is a (large) hyperparameter that regulates the importance of the performance/rejection trade-off expressed
inside the function l(𝜉i , 𝜀), and 𝛼i are the Lagrangian multipliers. Second, the two hyperplanes can be parametrized as

w� ⋅ x + b� = 0 and

w�� ⋅ x + b�� = 0.

By formulating two distinct optimization problems, one can learn the parameters of these
hyperplanes. In this approach, one hyperplane is highly penalized for mispredicting the
positive class, while the other one is for the negative class. Essentially, this technique yields
two SVMs that have few mispredictions on either class, and examples falling in between
the hyperplanes can be naturally rejected (Varshney, 2006). With the same approach, one
can also learn a OCSVM for each class to reject test examples that lie outside any learned
hypersphere (novelty) or within two overlapping hyperspheres (ambiguity) (Lotte et al.,
2008; Loeffel et al., 2015; Wu et al., 2007). Finally, Gamelas Sousa et al. (2014a) shows
that limiting the number of support vectors reduces the computational cost, while still
ensuring high performance in most cases.
However, in several cases, more than two SVMs are used. For instance, in multilabel classification one can exploit as many SVMs as the number of labels and fit each
hyperplane to discriminate between one class and all the others (Pillai et al., 2011).
This raises the issue of defining rejection in the regions of intersection between some,
but not all, of the hyperplanes. To address this, a natural solution is to utilize a datareplication method (Gamelas Sousa et al., 2009). This approach involves replicating
the complete dataset for each class k ∈ Y , adding a new dimension z with the class
number, changing the target variable of each replica to a discrete one-vs-all label,
and discriminating class k from the other classes (Cardoso & Pinto Da Costa, 2007;
da Rocha Neto et al., 2011).
Finally, Neural Network models allow integrating the rejector and predictor into the
same structure by modifying their output layers (Gangrade et al., 2021b; Ziyin et al.,
2019). Geifman and El-Yaniv (2019) propose to introduce an additional head mr into the
network that is dedicated to rejection. Specifically, mr is set as a sigmoid function and
used such that

m(x) = R

if mr (x) < 0.5.

Similar to the SVM case, Gasca A. et al. (2011) and Mesquita et al. (2016) measure the
disagreement of two Neural Networks trained to prioritize the classes differently. Specifically, they assume a binary classification task and use the output of two neural networks h1,
h2 to predict the positive class if h1 (x), h2 (x) ≥ 0, the negative class if h1 (x), h2 (x) < 0 and
rejection if they disagree on the sign. For this task, they use two weighted Extreme Learning Machines (wELM) (Zong et al., 2013), namely two neural networks with Q hidden
neurons that output

13

3093

Machine Learning (2024) 113:3073–3110

h∗ (x) =

Q
∑

wy 𝛽q g(aq ⋅ x + bq )

q=1

where wy is the cost related to the example x that belongs to the class y, aq is the weight
vector connecting the q-th hidden node and the input nodes, bq is the bias of the q-th hidden node and g is the activation function. By setting the class misprediction costs, learning
the parameters 𝛽 = (𝛽1 , … , 𝛽Q ) requires using the traditional weighted least square formulation min ‖H𝛽 − Y‖2 so that

𝛽 = (H T WH)−1 H T WY
where H is the n × Q matrix of activation functions hiq = g(aq ⋅ xi + bq ), W is the n × 1
matrix of class costs (one per example) and Y is the target vector. Thus, each network limits one class mispredictions and the region of disagreement is designed to be the rejection
region.
Benefits and drawbacks of an integrated rejector. This architecture has two key benefits.
First, integrating the predictor and rejector means that both aspects of the model are optimized toward the task at hand. This can improve the performance of the model with rejection when compared to using other architectures because the predictor’s and the rejector’s
components can affect each other. Second, because it is a unique model, the bias introduced
by the model with rejection is potentially less than in the scenario where the predictor and
rejector are two different models. However, this architecture has potential drawbacks, as
designing such a rejector might not be trivial. First, it requires extensive knowledge about
the predictor in order to integrate the reject option. Second, it may require developing a
novel algorithm to learn the model with a reject option from data. Finally, it is computationally more expensive than the other architectures, as any changes to the rejector require
retraining the entire model, which can be time-consuming (Clertant et al., 2020; Shpakova
& Sokolovska, 2021).

7 Combining multiple rejectors
Most rejectors are tailored towards a single rejection type. However, by combining multiple rejectors one can enable multiple rejections, such as performing both ambiguity and
novelty rejection. We distinguish between two types of combinations of rejectors based on
whether the rejectors’ rejection regions overlap or not because examples in overlapping
regions require deeper analysis (e.g., to specify the underlying rejection type).
First, when rejectors do not overlap (or when we are not interested in the example’s
rejection type), one can simply combine the rejection sets by a logical or-rule: reject
the example if any of the rejectors rejects it and assign such rejection type (Frélicot,
1997; Suutala et al., 2004). For instance, given Z rejectors r1 , r2 , … , rZ with thresholds
𝜏1 , 𝜏2 , … , 𝜏Z , one can combine them into m as
{
R
if ∃ i ≤ Z ∶ ri (x;h) < 𝜏i
m(x) =
h(x) otherwise
Second, when rejectors overlap in some regions a simple or-rule can be insufficient to
determine the reason for rejection because each rejector may decide to abstain for a different reason. Typically, existing works carefully select the order to evaluate the rejectors.

13

Machine Learning (2024) 113:3073–3110

3094

This is usually done in a multi-step architecture: either by stacking only the rejectors (Frélicot, 1998; Frélicot & Mascarilla, 2002), or even using multiple models with rejection (Pudil et al., 1992; Barandas et al., 2022). For instance, given Z rejectors r1 , r2 , … , rZ
with thresholds 𝜏1 , 𝜏2 , … , 𝜏Z , one can order rejectors by importance and combine them as

⎧ R1
⎪ R
m(x) = ⎨ 2
⎪⋮
⎩ h(x)

if r1 (x;h) < 𝜏1 ;
if r1 (x;h) ≥ 𝜏1 and r2 (x;h) < 𝜏2 ;
if ri (x;h) ≥ 𝜏i ∀ i ≤ Z;

where R i indicates the rejector ri ’s type of rejection.

8 Applications of machine learning models with rejection
In safety-sensitive domains, making the wrong decision can have serious consequences
such as fatal accidents with self-driving cars, major breakdowns in industrial settings or
incorrect diagnoses in medical applications. In these domains, rejection can be used to
make cautious predictions. However, the number of papers discussing machine learning
with rejection in practical applications is still limited. In this section, an overview of these
papers is given.
Biomedical applications. Machine learning with rejection is primarily explored in medical applications due to the potential consequences of incorrect decisions (Liu et al., 2022).
The main focus is on ambiguity rejection for medical diagnosing, specifically the detection
and classification of diseases. If the model is confident enough, the detection results are
automatically translated into a diagnosis. Otherwise, a medical expert verifies the detection (Kompa et al., 2021). For instance, vocal pathologies are detected using voice recording data, where a linear classifier is trained and uncertain predictions are rejected based
on a threshold of the derived posterior probability (Kotropoulos & Arce, 2009). Spine disease diagnosis employs the data-replication method, which predicts only when two biased
classifiers agree (Gamelas Sousa et al., 2009). Cancer detection, particularly breast tumor
detection, benefits from a reject option implemented with an SVM classifier using confidence-based rejection (Guan et al., 2020). The rejection thresholds are chosen to limit the
rejection rate and reduce manual effort.
Other biomedical applications have also adopted the use of a reject option. Lotte et al.
(2008) conduct an experiment on distinguishing hand movements using brain activity. They
employ a separate novelty rejector trained in a supervised manner to discard brain activity
associated with other activities. Lewicke et al. (2008) explore sleep stage scoring with both
types of rejection, utilizing confidence metrics derived from a Neural Network classifier’s
neural activities. Another sleep stage scoring application utilizes a separate rejector based
on Local Outlier Factor (LOF) anomaly scores for novelty rejection, identifying patients
who deviate from the training data (Van der Plas et al., 2021). Some papers compare the
performance of multiple models with rejection to determine the optimal approach for specific biomedical applications. For instance, Kang et al. (2017) predict the effectiveness of a
diabetes drug for individual patients, while Tang and Sazonov (2014) investigate the classification of body positions using sensors placed in patients’ shoes. Lastly, a medical application focuses on the analysis of tissue examples, aiming to classify each pixel of tissue
images into categories such as bone, fat, or muscle (Condessa et al., 2013, 2015a).

13

Machine Learning (2024) 113:3073–3110

3095

Engineering applications. Applications in engineering can also benefit from a reject
option. For instance, in the chemical identification of gases, time-series data is processed
by two classifiers to classify the observed gas. Classification occurs only when there is
agreement between the classifiers, and ambiguous predictions are rejected until consensus is reached (Hatami & Chira, 2013). A similar ambiguity rejection technique, rejecting when two classifiers disagree, is employed in defect detection in software applications (Mesquita et al., 2016). Fault detection in steam generators utilizes a set of one
against all SVM classifiers, and rejection is based on the distance to the decision boundary
of these classifiers, allowing for both rejection types (Zou et al., 2011). Finally, Hendrickx
et al. (2022) employs a separated novelty rejector for vehicle usage profiling.
Economics applications. In the domain of economics, two applications of machine
learning with rejection have been proposed, both focused on ambiguity rejection and novelty rejection. The first application uses a Learning Vector Quantization (LVQ) to classify
dollar bills by value (Ahmadi et al., 2004). Confidence metrics are obtained from the classifier for both types of rejection. The second application investigates a few rejection techniques on top of a predictor to decide whether to grant a loan (Coenen et al., 2020)
Image recognition applications. Reject options are usually available for analyzing text
styles and reading handwritten numbers (Fumera & Roli, 2004), used for both ambiguity
rejection (Xu et al., 1992; Huang & Suen, 1995; Rahman & Fairhurst, 1998) and novelty
rejection (Lou et al., 1999; Arlandis et al., 2002). These methods employ a confidencebased dependent rejector. Additionally, there is a paper focused on identifying walkers
based on their footprints (Suutala et al., 2004). Initially, each footprint is individually predicted or rejected, and then the information from three consecutive footprints is combined
for the final decision.

9 Link to other research areas
This section briefly discusses the fields related to learning with rejection.

9.1 Uncertainty quantification
The field of uncertainty quantification (UQ) aims to measure how uncertain a learned
model’s predictions are (Gal et al., 2017). It distinguishes between two types of uncertainties: aleatoric uncertainty, which is the randomness in the data, and epistemic uncertainty,
which is the lack of knowledge. Aleatoric uncertainty arises from non-deterministic relations between features and the target, while epistemic uncertainty can be caused by a small
training set or incorrect model bias. For instance, when predicting the outcome of tossing
an unfair coin, initially we lack historical data, resulting in high data-epistemic uncertainty.
As we observe more coin tosses, data-epistemic uncertainty decreases, but aleatoric uncertainty remains due to the stochastic nature of the coin flip (Senge et al., 2014).
These uncertainties are inherently related to rejection. Rejecting examples due to high
aleatoric uncertainty falls into the ambiguity rejection scenario. On the other hand, high
epistemic uncertainty due to the lack of data may cause either ambiguity or novelty rejection. That is, if an example is similar to the training set but its prediction strongly depends
on the choice of the dataset (e.g., close to the predictor’s decision boundary for classification tasks), then this gives rise to an ambiguity rejection. Alternatively, if an example is
dissimilar to any of the training examples, this leads to a novelty rejection.

13

3096

Machine Learning (2024) 113:3073–3110

Methods for UQ can be applied within learning with rejection. UQ focuses on obtaining
(calibrated) estimates that meaningfully convey the level of uncertainty (Kotelevskii et al.,
2022), which learning with rejection can leverage to allow the model to abstain when the
uncertainty is high (Perello-Nieto et al., 2017; Kompa et al., 2021). While calibrated uncertainty estimates are not always necessary for learning with rejection, they can be important.
For instance, calibrated uncertainty estimates enable setting an optimal threshold that minimizes the empirical risks (Chow, 1970).

9.2 Anomaly detection
Anomaly detection (Prasad et al., 2009) is a Data Mining task aimed at identifying examples that deviate from expected behavior in a dataset. It is closely linked to novelty rejection because anomalies, being rare and substantially different from the training data, fall
under the category of novelties (Ulmer & Cinàa 2020; Pimentel et al. 2014; Markou &
Singh 2003). Anomaly detectors are often utilized for novelty rejection within a separate
rejector architecture.
Adding a reject option to anomaly detectors allows them to abstain from processing
examples when a clear decision cannot be made (Perini et al., 2020b, 2023). However,
enabling this option in unsupervised anomaly detection poses two challenges. First, most
confidence metrics assume a supervised setting, relying on measuring the distance to a
decision surface. However, in anomaly detection, a hard decision surface may not always
exist, necessitating specialized metrics that consider the model bias of the detector (Perini
et al., 2020b). Second, the lack of labeled data makes it difficult to train a rejector using
standard performance metrics. Instead, unsupervised techniques are employed, leveraging
performance metrics that measure the stability of the anomaly detector itself (Perini et al.,
2020a).

9.3 Active learning
Active learning (Settles, 2009; Fu et al., 2013; Zhang & Chaudhuri, 2014; Nguyen et al.,
2019) involves the interaction between a learning algorithm and an oracle who provides
feedback to guide the learner. Its purpose is to reduce the need for labeling large amounts
of data while still achieving high predictive performance. The algorithms focus on identifying the examples that would be most beneficial for the learner to label, thus minimizing
the associated labeling costs.
Active learning and learning with rejection share the focus on uncertain examples (Amin et al., 2021). However, they differ in their motivations for addressing uncertainty. In active learning, uncertainty is crucial during training to improve efficiency by
minimizing the amount of labeled data required for an accurate model. In contrast, learning
with rejection aims to capture uncertainty at test time to prevent mispredictions. Its focus is
on avoiding unreliable predictions based on uncertain examples.
Another difference is that outliers are not always considered. For instance, methods
based on discriminative learning cannot express low-density regions. Sharma and Bilgic
(2017) determine uncertain examples based on evidence measures that support the positive
( E+1) or negative class ( E−1) in binary classification. An example x has an uncertain class
if E+1 (x) ≈ E−1 (x). Two cases are distinguished based on the magnitude of the evidence:
if both E+1 and E−1 are large, the model is uncertain because of strong, but conflicting evidence for both classes, while if both E+1 and E−1 are small, the model is uncertain because

13

Machine Learning (2024) 113:3073–3110

3097

of insufficient evidence for either class. Because both cases assume that a model is uncertain if P(Y|X) ≈ 0.5 when using a uniform prior, they both correspond to our ambiguity
rejection scenario.
Combining active learning with machine learning with rejection could be of great
use (Korycki et al., 2019; Puchkin & Zhivotovskiy, 2022; Shekhar et al., 2020). When the
interaction with an oracle is possible, it may be of interest to query the rejected test examples. New data types could be identified by novelty rejection, while ambiguity rejection
may fine-tune the decision boundary.

9.4 Class‑incremental/incomplete learning
Typically, learned models assume knowledge of all possible classes during training. However, class-incremental learning focuses on models that adapt during deployment to detect
and predict novel classes that were not seen during training.
Novelty rejection and class-incremental learning both operate under an open-world
assumption and aim to detect novel examples compared to the training set. However, there
are two key differences. First, class-incremental learning specifically targets examples
belonging to novel classes, distinguishing them from outliers. In contrast, novelty rejection
techniques do not prioritize this distinction. Second, class-incremental learning involves
detecting novel class examples and retraining the model to recognize them.
Novelty rejection techniques can be considered in class-incremental learning. Moreover,
both techniques can be combined into a single pipeline, by adapting incremental models
with novelty rejected examples. For instance, such examples can be used as prototypes in a
k-Nearest Neighbors (k-NN) model.

9.5 Delegating classifiers
Similar to learning with rejection, the approach of delegation involves the use of a classifier, which only classifies examples with high confidence and delegates the prediction for
the remaining examples (Temanni & Nadeem, 2007; Khodra, 2016). The delegated examples are given to another, more specialized, classifier which makes a prediction (Ferri et al.,
2004; Prasad & Sowmya, 2008). In contrast, learning with rejection usually assumes that
the user will inspect any rejected examples. Furthermore, delegation can be developed as a
chain, where the next classifier makes a prediction for the examples for which the previous
model was too uncertain (Giraud-Carrier, 2022).

9.6 Meta‑learning
Meta-learning, also known as “learning to learn”, explores methods and techniques for
automatically learning the characteristics, behaviors, and performance of machine learning
models (Bock, 1988; Vanschoren, 2018). It aims to develop higher-level knowledge that
guides the learning process itself (Brazdil et al., 2009; Gridin, 2022).
Despite having different goals and levels of abstraction, meta-learning can provide valuable insights and approaches for the context of learning with rejection. For instance, metalearning algorithms analyze the behavior and performance of classifiers on different datasets to derive general knowledge about their strengths, weaknesses, and limitations (Abbasi
et al., 2012; Tremmel et al., 2022; Cohen et al., 2022). This knowledge can then be used to

13

3098

Machine Learning (2024) 113:3073–3110

make informed decisions about when to reject predictions. Moreover, meta-learning algorithms can identify relevant features or attributes that are informative for determining when
to reject predictions (Filchenkov & Pendryak, 2016; Shen et al., 2020b). By focusing on
important features, rejectors can make more accurate decisions.

10 Conclusions and perspectives
We have studied the subfield of machine learning with rejection and provided a higherlevel overview of existing research. To conclude, we revisit our key research questions and
point to new directions that future research might take.

10.1 Research questions revisited
This survey paper is built around eight key research questions, introduced in the introduction. In this section, we revisit each of these questions and briefly summarize our findings.
How can we formalize the conditions for which a model should abstain from making a
prediction? In Sect. 2, we identify two types of rejections: ambiguity rejection and novelty rejection. Ambiguity rejection abstains from making a prediction an example falls in
a region where the target value is ambiguous (e.g., close to the decision boundary in classification tasks). This could be due to a non-deterministic true relation between the features
and target variable, or due to a hypothesis space that is not able to capture the true relation.
Novelty rejection abstains from making a prediction on examples that are rare with respect
to the given training set. For such an example, there is no guarantee that the model correctly extrapolates to this untrained region, making it likely that the model mispredicts the
example.
How can we evaluate the performance of a model with rejection? Standard machine
learning evaluation is focused on a model’s predictive quality. However, in machine learning with rejection, there exists a trade-off between the predictive quality and the proportion
of rejected examples.
In Sect. 3, we provide an overview of techniques evaluating both the prediction and
rejection quality of models with rejection. We identify three categories: metrics evaluating
models with a given rejection rate, metrics evaluating the overall model performance/rejection trade-off, and metrics evaluating models through a cost function.
What architectures are possible for operationalizing (i.e., putting this into practice) the
ability to abstain from making a prediction? We categorize machine learning methodologies with rejection in three different architectures, depending on the relationship between
the predictor and the rejector: separated, dependent and integrated rejector. These categories are introduced and mapped to the existing literature in Sects. 4, 5 and 6.
How do we learn models with rejection? For each architecture, we discuss the main
techniques to learn a model with rejection and related these to the existing literature in
Sects. 4, 5 and 6. First, the separated rejector is usually learned independently of the predictor. Second, learning the dependent rejector entails learning for which examples the
predictor is likely to mispredict using a confidence function. Both architectures need setting a rejection threshold. Third, integrated rejector needs a unique algorithm for learning
predictor and rejector in tandem. Usually, this architecture relies on designing an objective
function.

13

Machine Learning (2024) 113:3073–3110

3099

What are the main pros and cons of using a specific architecture? Each architecture,
discussed in Sects. 4,5, and 6, offers distinct benefits and drawbacks. Separated rejectors
show broad applicability, as they can be combined with any predictor. However, they often
yield sub-optimal rejection performance since they do not learn from the predictor’s mispredictions. On the other hand, dependent rejectors have reduced, yet still high, applicability, relying on a specific confidence function learned from the predictor’s output, but they
can enhance the rejection quality by leveraging the predictor’s mispredictions. Finally, integrated rejectors necessitate joint design with the predictor, but learning a single model for
prediction and rejection improves the overall performance for both prediction and rejection
tasks.
How can we combine multiple rejectors? We discuss the combination of multiple
rejectors for enabling various types of rejections within a unique model. There are two
approaches for combining rejectors. First, when rejectors do not overlap, a logical “or”
rule is applied, rejecting an example if any of the rejectors rejects it. Second, when rejectors overlap in some regions and disagree on the type of rejection, a multi-step architecture
is used, ordering rejectors by importance to make decisions based on the most relevant
rejector.
Where does the need for machine learning with rejection methods arise in real-world
applications? On a high level, machine learning with rejection is typically used in applications where incorrect decisions can have severe consequences, both financially and safetyrelated. These consequences motivate the need for robust and trustworthy machine learning. In Sect. 8, we provide an overview of application areas in which machine learning
with rejection is already used.
How does machine learning with rejection relate to other research areas? Section 9
shows that machine learning with rejection is closely related to several other subfields of
machine learning. This relation sometimes leads to terminology and techniques overlapping or inspired by these other domains. In contrast, other cases show machine learning
with rejection from a broader perspective. In this survey, we related machine learning with
rejection to uncertainty quantification, anomaly detection, active learning, class-incremental learning, delegating classifiers, and meta-learning.

10.2 Future directions
Given its significance for the usage of machine learning in real-world problems and the
growing attention for trustworthy AI, we expect machine learning with rejection to remain
an active research field. In this section, we briefly discuss three key research directions for
which we see a strong need.
Standard settings to compare different models with rejection. A large number of
machine learning models with rejection already exist. However, these are typically evaluated on custom or even proprietary data. This makes it difficult to benchmark and compare
the different approaches. While some papers use publicly available datasets, there is no
standard benchmark set for machine learning with rejection. Additionally, applying multiple strategies to evaluate the rejector offers a better view of an algorithm’s performance
and improves comparability.
Partial rejection for machine learning models. A promising avenue for further exploration is the concept of partial abstention. Nowadays, machine learning problems often
involve seeking elaborated predictions rather than simple scalar or class values as in classification and regression tasks. For instance, in multi-label classification, a prediction

13

3100

Machine Learning (2024) 113:3073–3110

for an instance is a subset of possible class labels. In such cases, the idea of abstaining
from a complete prediction can be extended to partial abstention, where the learner delivers predictions on some but not necessarily all class labels, according to its level of certainty (Nguyen & Hüllermeier, 2020). This has the key benefit of providing a middle
ground between making predictions for the entire structure and completely abstaining from
making any predictions.
Algorithms enabling models with rejection in domains other than classification. Most
papers on machine learning with rejection study supervised classification problems. Modern machine learning tackles numerous other tasks such as regression, forecasting, and
clustering, or even semi-supervised and self-supervised feedback loops. We believe that
the rejection can also be of use in such areas. However, since only a handful of relevant
studies exist, this requires more attention from the research community. Future research
can also focus on integrating rejection-related variables into statistical frameworks utilized
in educational measurement, such as Item Response Theory (IRT). This integration has
the potential to improve the precision of item calibration, trait estimation, and the interpretation of test scores. Furthermore, it can provide valuable insights into the psychological
aspects of learning, enabling the development of more precise instructional strategies and
interventions.
Author contributions Concept: JD, WM; Literature Study: KH, LP, DVdP; Categorization: KH, LP, DVdP,
WM, JD; Writing - original draft preparation: KH, LP, DVdP; Writing - review and editing: WM, JD; Writing - revision: LP, WM, JD, DVdP, KH; Funding acquisition: WM, JD; Supervision: WM, JD.
Funding Kilian Hendrickx and Dries Van der Plas received funding from VLAIO (Flemish Innovation &
Entrepreneurship) through the Baekeland PhD mandates [HBC.2017.0226] (KH) and [HBC.2019.2615]
(DV). Lorenzo Perini received funding from FWO-Vlaanderen, aspirant grant 1166222N. Jesse Davis is partially supported by the KU Leuven research funds [C14/17/070]. Lorenzo Perini, Jesse Davis and Wannes
Meert received funding from the Flemish Government under the “Onderzoeksprogramma Artificiële Intelligentie (AI) Vlaanderen” programme.
Availability of data and material Not applicable.
Code availability Not applicable.

Declarations
Conflict of interest The authors declare that they have no Conflict of interest.
Ethical approval Not applicable.
Consent to participate Not applicable.

References
Abbas, M. R., Nadeem, M. S. A., Shaheen, A., Alshdadi, A. A., Alharbey, R., Shim, S.-O., & Aziz, W.
(2019). Accuracy rejection normalized-cost curves (ARNCCs): A novel 3-dimensional framework for
robust classification. IEEE Access, 7, 160125–160143.
Abbasi, A., Albrecht, C., Vance, A., & Hansen, J. (2012). Metafraud: A meta-learning framework for detecting financial fraud. MIS Quarterly: Management Information Systems, 36(4), 1293–1327.
Ahmadi, A., Omatu, S., Fujinaka, T., & Kosaka, T. (2004). Improvement of reliability in banknote classification using reject option and local PCA. Information Sciences, 168(1–4), 277–293.
Alhoniemi, E., Himberg, J., & Vesanto, J. (1999). Probabilistic measures for responses of self-organizing
map units. In H. Bothe, E. Oja, E. Massad and C. Haefke, (eds.), Proceedings of the international

13

Machine Learning (2024) 113:3073–3110

3101

ICSC congress on computational intelligence methods and applications. ICSC Academic Press,
Zurich, Switzerland, (pp. 286–290). ICSC Academic Press.
Amin, K., DeSalvo, G., & Rostamizadeh, A. (2021). Learning with labeling induced abstentions. Advances
in Neural Information Processing Systems, 15(NeurIPS), 12576–12586.
Arlandis, J., Perez-Cortes, J. C., & Cano, J. (2002). Rejection strategies and confidence measures for a k-NN
classifier in an OCR task. In International Conference on Pattern Recognition, (vol. 16, pp. 576–579).
Asif, A., & Minhas, F. u. A. A. (2020). Generalized Neural Framework for Learning with Rejection. In 2020
International Joint Conference on Neural Networks (IJCNN), (pp. 1–8). IEEE.
Balsubramani, A. (2016). Learning to abstain from binary prediction, (pp. 1–23). arXiv preprintarXiv:​1602.​
08151
Barandas, M., Folgado, D., Santos, R., Simão, R., & Gamboa, H. (2022). Uncertainty-based rejection in
machine learning: Implications for model development and interpretability. Electronics (Switzerland),
11(3), 1–20.
Bartlett, P. L., & Wegkamp, M. H. (2008). Classification with a reject option using a hinge loss. Journal of
Machine Learning Research, 9, 1823–1840.
Berlemont, S., Lefebvre, G., Duffner, S., & Garcia, C. (2015). Siamese neural network based similarity metric for inertial gesture classification and rejection. In 2015 11th IEEE International Conference and
Workshops on Automatic Face and Gesture Recognition (FG), (pp. 1–6). IEEE.
Bock, P. (1988). A perspective on artificial intelligence: Learning to learn. Annals of Operations Research,
16(1), 33–52.
Boulegane, D., Bifet, A., & Madhusudan, G. (2019). Arbitrated dynamic ensemble with abstaining for timeseries forecasting on data streams. In 2019 IEEE international conference on big data (big data), (pp.
1040–1045). IEEE.
Bounsiar, A., Beauseroy, P., & Grall-Maës, E. (2008). General solution and learning method for binary classification with performance constraints. Pattern Recognition Letters, 29(10), 1455–1465.
Brazdil, P., Carrier, C. G., Soares, C., & Vilalta, R. (2009). Metalearning—Applications to Data Mining.
Springer Science & Business Media.
Brinkrolf, J., & Hammer, B. (2017). Probabilistic extension and reject options for pairwise LVQ. In 2017
12th international workshop on self-organizing maps and learning vector quantization, clustering
and data visualization (WSOM), (pp. 1–8). IEEE.
Brinkrolf, J., & Hammer, B. (2018). Interpretable machine learning with reject option. Automatisierungstechnik, 66(4), 283–290.
Cao, Y., Cai, T., & An, B. (2022). Generalizing consistent multi-class classification with rejection to be
compatible with arbitrary losses. (NeurIPS), (pp. 1–14).
Cardoso, J. S., & Pinto Da Costa, J. F. (2007). Learning to classify ordinal data: The data replication
method. Journal of Machine Learning Research, 8, 1393–1429.
Cecotti, H., & Vajda, S. (2013). Rejection schemes in multi-class classification—Application to handwritten
character recognition. In 2013 12th international conference on document analysis and recognition,
(pp. 445–449). IEEE.
Charoenphakdee, N., Cui, Z., Zhang, Y., & Sugiyama, M. (2021). Classification with rejection based on
cost-sensitive classification. In Proceedings of the 38th international conference on machine learning,
(pp. 1507–1517).
Chen, B., Chen, B. F., & Lin, H. T. (2018). Rotation-blended CNNs on a new open dataset for tropical
cyclone image-to-intensity regression. Proceedings of the ACM SIGKDD international conference on
knowledge discovery and data mining, (pp. 90–99).
Chow, C. (1970). On optimum recognition error and reject tradeoff. IEEE Transactions on Information Theory, 16(1), 41–46.
Clertant, M., Sokolovska, N., Chevaleyre, Y., & Hanczar, B. (2020). Interpretable cascade classifiers with
abstention. In AISTATS 2019 - 22nd international conference on artificial intelligence and statistics.
Coenen, L., Abdullah, A. K., & Guns, T. (2020). Probability of default estimation, with a reject option. In
2020 IEEE 7th international conference on data science and advanced analytics (DSAA), (pp. 439–
448). IEEE.
Cohen, K. M., Park, S., Simeone, O., & Shamai, S. (2022). Bayesian active meta-learning for reliable and
efficient AI-based demodulation. IEEE Transactions on Signal Processing, 70, 5366–5380.
Condessa, F., Bioucas-Dias, J., Castro, C. A., Ozolek, J., & Kovacevic, J. (2013). Classification with reject
option using contextual information. In 2013 IEEE 10th international symposium on biomedical
imaging, (pp. 1340–1343), San Francisco, California. IEEE.
Condessa, F., Bioucas-Dias, J., Castro, C. A., Ozolek, J., & Kovačević, J. (2015a). Image classification with
rejection using contextual information, (pp. 1–21). arXiv preprintarXiv:​1509.​01287

13

3102

Machine Learning (2024) 113:3073–3110

Condessa, F., Bioucas-Dias, J., & Kovacevic, J. (2015b). Robust hyperspectral image classification with
rejection fields. In Workshop on hyperspectral image and signal processing, evolution in remote sensing, (vol. 2015-June, pp. 1–4), Tokyo, Japan. IEEE.
Condessa, F., Bioucas-Dias, J., & Kovacevic, J. (2015). Supervised hyperspectral image classification with
rejection. IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing, 9(6),
2321–2332.
Condessa, F., Bioucas-Dias, J., & Kovačević, J. (2017). Performance measures for classification systems
with rejection. Pattern Recognition, 63, 437–450.
Conte, D., Foggia, P., Percannella, G., Saggese, A., & Vento, M. (2012). An ensemble of rejecting classifiers for anomaly detection of audio events. In Proceedings - 2012 IEEE 9th international conference
on advanced video and signal-based surveillance, AVSS 2012, (pp. 76–81). IEEE.
Corbière, C., Thome, N., Saporta, A., Vu, T. H., Cord, M., & Pérez, P. (2022). Confidence estimation
via auxiliary models. IEEE Transactions on Pattern Analysis and Machine Intelligence, 44(10),
6043–6055.
Cordelia, L. P., Foggia, P., Sansone, C., Tortorella, F., & Vento, M. (1998). Optimizing the error/reject
trade-off for a multi-expert system using the Bayesian combining rule. In lecture notes in computer
science (including subseries lecture notes in artificial intelligence and lecture notes in bioinformatics), (vol. 1451, pp. 717–725).
Cordella, L., De Stefano, C., Fontanella, F., & Scotto Di Freca, A. S. (2014). Random forest for reliable
pre-classification of handwritten characters. In Proceedings—international conference on pattern recognition, (pp. 1319–1324). IEEE.
Cordella, L., De Stefano, C., Sansone, C., & Vento, M. (1995). An adaptive reject option for LVQ classifiers. Lecture notes in computer science (vol. 974, pp. 68–73). Springer.
Cordella, L., De Stefano, C., Tortorella, F., & Vento, M. (1995). A method for improving classification reliability of multilayer perceptrons. IEEE Transactions on Neural Networks, 6(5), 1140–1147.
Cortes, C., DeSalvo, G., Gentile, C., Mohri, M., & Yang, S. (2018). Online Learning with Abstention. In
Proceedings of the 35th international conference on machine learning, volume 80 of Proceedings of
machine learning research, (pp. 1059–1067), Stockholmsmässan, Stockholm Sweden. PMLR.
Cortes, C., DeSalvo, G., & Mohri, M. (2016a). Boosting with abstention. In Advances in neural information
processing systems, (pp. 1668–1676).
Cortes, C., DeSalvo, G., & Mohri, M. (2016b). Learning with Rejection. In Proceedings of The 27th international conference on algorithmic learning theory (ALT 2016), volume 9925 LNAI, (pp. 67–82),
Bari, Italy. Springer.
da Rocha Neto, A. R., Sousa, R., Barreto, G. A., & Cardoso, J. S. (2011). Diagnostic of pathology on the
vertebral column with embedded reject option. In IbPRIA 2011: pattern recognition and image analysis, (vol. 6669 LNCS, pp. 588–595).
Dalitz, C. (2009). Reject options and confidence measures for kNN classifiers. Schriftenreihe des Fachbereichs Elektrotechnik und Informatik Hochschule Niederrhein, 8(2009), 16–38.
De, A., Okati, N., Zarezade, A., & Rodriguez, M. G. (2021). Classification Under Human Assistance. In
35th AAAI conference on artificial intelligence, AAAI 2021, (vol. 7, pp. 5905–5913).
De Stefano, C., Sansone, C., & Vento, M. (2000). To reject or not to reject: That is the question-an answer in
case of neural classifiers. IEEE Transactions on Systems, Man and Cybernetics, Part C (Applications
and Reviews), 30(1), 84–94.
Denis, C., & Hebiri, M. (2020). Consistency of plug-in confidence sets for classification in semi-supervised
learning. Journal of Nonparametric Statistics, 32(1), 42–72.
Devos, L., Meert, W., & Davis, J. (2021). Versatile verification of tree ensembles. Proceedings of Machine
Learning Research, 139, 2654–2664.
Devos, L., Perini, L., Meert, W., & Davis, J. (2023). Detecting evasion attacks in deployed tree ensembles. In Joint European conference on machine learning and knowledge discovery in databases, (pp.
227–243).
Du, J., Ni, E. A., & Ling, C. X. (2010). Adapting cost-sensitive learning for reject option. In International
conference on information and knowledge management, proceedings, (pp. 1865–1868).
Dubos, C., Bernard, S., Adam, S., & Sabourin, R. (2016). ROC-based cost-sensitive classification with a
reject option. In 2016 23rd international conference on pattern recognition (ICPR), (pp. 3320–3325).
IEEE.
Dubuisson, B., & Masson, M. (1993). A statistical decision rule with incomplete knowledge about classes.
Pattern Recognition, 26(1), 155–165.
Dübuisson, B., Usai, M., & Malvache, P. (1985). Computer aided system diagnostic with an incomplete
learning set. Progress in Nuclear Energy, 15(C), 875–880.

13

Machine Learning (2024) 113:3073–3110

3103

El-Yaniv, R., & Wiener, Y. (2010). On the foundations of noise-free selective classification. Journal of
Machine Learning Research, 11, 1605–1641.
El-Yaniv, R., & Wiener, Y. (2011). Agnostic selective classification. Advances in Neural Information
Processing Systems, 24, 1–9.
Feng, L., Ahmed, M. O., Hajimirsadeghi, H., & Abdi, A. (2022). Towards Better Selective Classification. In International conference on learning and representation.
Ferri, C., Flach, P., & Hernández-Orallo, J. (2004). Delegating classifiers. Proceedings, twenty-first
international conference on machine learning, ICML, 2004, (pp. 289–296).
Ferri, C., & Hernández-Orallo, J. (2004). Cautious lassifiers. Proceedings of ROC analysis in artificial
intelligence, 1st international workshop (ROCAI-2004), (pp. 27–36).
Filchenkov, A., & Pendryak, A. (2016). Datasets meta-feature description for recommending feature
selection algorithm. In Proceedings of artificial intelligence and natural language and information extraction, social media and web search FRUCT conference, AINL-ISMW FRUCT, 2015,
(vol. 7, pp. 11–18).
Fischer, L., Hammer, B., & Wersing, H. (2014a). Local rejection strategies for learning vector quantization. In Lecture notes in computer science, volume 8681 LNCS, (pp. 563–570). Springer.
Fischer, L., Hammer, B., & Wersing, H. (2015). Efficient rejection strategies for prototype-based classification. Neurocomputing, 169, 334–342.
Fischer, L., Hammer, B., & Wersing, H. (2015b). Optimum reject options for prototype-based classification. arXiv preprintarXiv:​1503.​06549.
Fischer, L., Hammer, B., & Wersing, H. (2016). Optimal local rejection for classifiers. Neurocomputing,
214, 445–457.
Fischer, L., Nebel, D., Villmann, T., Hammer, B., & Wersing, H. (2014b). Rejection strategies for learning vector quantization - a comparison of probabilistic and deterministic approaches. In 22nd
European symposium on artificial neural networks, computational intelligence and machine learning, ESANN 2014 - roceedings, (pp. 109–118). Springer.
Fischer, L. & Villmann, T. (2016). A probabilistic classifier model with adaptive rejection option. http://​
www.​techf​ak.​uni-​biele​feld.​de/​~fschl​eif/​mlr/​mlr.​html.
Flores, I. (1958). An optimum character recognition system using decision functions. IRE Transactions
on Electronic Computers, EC–7(2), 180.
Franc, V., & Prusa, D. (2019). On discriminative learning of prediction uncertainty. In 36th international conference on machine learning, ICML 2019, 2019-June, (pp. 3465–3480).
Franc, V., Prusa, D., & Voracek, V. (2021). Optimal strategies for reject option classifiers. Journal of
Machine Learning Research, 24, 1–49.
Frélicot, C. (1997). Learning rejection thresholds for a class of fuzzy classifiers from possibilistic clustered noisy data. In 7th International fuzzy systems association world congress, IFSA, (vol. 3, pp.
111–116).
Frélicot, C. (1998). On unifying probabilistic/fuzzy and possibilistic rejection-based classifiers. SSPR /
SPR 1998: Advances in Pattern Recognition (pp. 736–745). Springer.
Frélicot, C., & Mascarilla, L. (2002). Reject strategies driven combination of pattern classifiers. Pattern
Analysis and Applications, 5(2), 234–243.
Friedel, C. C., Rückert, U., & Kramer, S. (2006). Cost Curves for Abstaining Classifiers. In ICML 2006 3th workshop ROC analysis in ML, Pittsburgh, Pennsylvania.
Fu, Y., Zhu, X., & Li, B. (2013). A survey on instance selection for active learning. Knowledge and
Information Systems, 35(2), 249–283.
Fukunaga, K., & Kessell, D. (1972). Application of optimum error-reject functions. IEEE Transactions
on Information Theory, 18(6), 814–817.
Fumera, G., Pillai, I., & Roli, F. (2003). Classification with reject option in text categorisation systems.
In 12th international conference on image analysis and processing, 2003. Proceedings, (pp. 582–
587). IEEE Comput. Soc.
Fumera, G., Pillai, I., & Roli, F. (2004). A two-stage classifier with reject option for text categorisation.
Lecture Notes in Computer Science (Vol. 3138, pp. 771–779). Springer.
Fumera, G., & Roli, F. (2002). Support vector machines with embedded reject option. In Pattern recognition with support vector machines (pp. 68–82). Springer.
Fumera, G., & Roli, F. (2004). Analysis of error-reject trade-off in linearly combined multiple classifiers.
Pattern Recognition, 37(6), 1245–1265.
Fumera, G., Roli, F., & Giacinto, G. (2000). Multiple reject thresholds for improving classification reliability. In Lecture notes in computer science, volume 1876 LNCS (pp. 863–871). Springer.
Gal, Y., Hron, J., & Kendall, A. (2017). Concrete Dropout. In Advances in neural information processing systems, (vol. 30, pp. 3581–3590). Curran Associates, Inc.

13

3104

Machine Learning (2024) 113:3073–3110

Gamelas Sousa, R., da Rocha-Neto, A. R., Cardoso, J. S., & Barreto, G. A. (2015). Robust classification with reject option using the self-organizing map. Neural Computing and Applications, 26(7),
1603–1619.
Gamelas Sousa, R., da Rocha Neto, A. R., Barreto, G. A., Cardoso, J. S., & Coimbra, M. T. (2014a). Reject
option paradigm for the reduction of support vectors. 22nd European symposium on artificial neural networks, computational intelligence and machine learning, ESANN 2014 - Proceedings, (pp.
331–336).
Gamelas Sousa, R., da Rocha Neto, A. R., Cardoso, J. S., & Barreto, G. A. (2014). Classification with reject
option using the self-organizing map. In Lecture notes in computer science, volume 8681 LNCS,
chapter Artificial, (pp. 105–112). Springer.
Gamelas Sousa, R., Mora, B., & Cardoso, J. S. (2009). An ordinal data method for the classification with
reject option. In 8th international conference on machine learning and applications, ICMLA 2009,
(vol. 2, pp. 746–750).
Gangrade, A., Kag, A., Cutkosky, A., & Saligrama, V. (2021). Online selective classification with limited
feedback. Advances in Neural Information Processing Systems, 18(NeurIPS), 14529–14541.
Gangrade, A., Kag, A., & Saligrama, V. (2021b). Selective classification via one-sided prediction. In Proceedings of the 24th international conference on artificial intelligence and statistics (AISTATS), (vol.
130, p. 22), San Diego, California, USA. Proceedings of Machine Learning Research.
Gasca, A., & E., Saldaña T., S., Sánchez G., J. S., Velásquez G., V., Rendón L., E., Abundez B., I. M., Valdovinos R., R. M., & Cruz R., R. (2011). A rejection option for the multilayer perceptron using hyperplanes. In Lecture notes in computer science, (vol. 6593 LNCS, pp. 51–60). Springer.
Geifman, Y., & El-Yaniv, R. (2017). Selective classification for deep neural networks. In Advances in neural
information processing systems, (pp. 4879–4888). Curran Associates, Inc.
Geifman, Y., & El-Yaniv, R. (2019). SelectiveNet: A deep neural network with an integrated reject option.
In International conference on machine learning (ICML 2019), (vol. 2019-June, pp. 3768–3776).
Giraud-Carrier, C. (2022). Combining base-learners into ensembles. Springer International Publishing.
Glodek, M., Schels, M., Palm, G., & Schwenker, F. (2012). Multiple classifier combination using reject
options and markov fusion networks. In ICMI’12 - Proceedings of the ACM international conference
on multimodal interaction, (pp. 465–472).
Golfarelli, M., Maio, D., & Malton, D. (1997). On the error-reject trade-off in biometric verification systems. IEEE Transactions on Pattern Analysis and Machine Intelligence, 19(7), 786–796.
Göpfert, J. P., Hammer, B., & Wersing, H. (2018). Mitigating concept drift via rejection. In Lecture notes in
computer science, volume 11139 LNCS, (pp. 456–467). Springer.
Grandvalet, Y., Rakotomamonjy, A., Keshet, J., & Canu, S. (2009). Support vector machines with a reject
option. In Advances in neural information processing systems, (vol. 21, pp. 537–544). Curran Associates, Inc.
Gridin, I. (2022). Hyperparameter Optimization.
Guan, H., Zhang, Y., Cheng, H. D., & Tang, X. (2020). Bounded-abstaining classification for breast tumors
in imbalanced ultrasound images. International Journal of Applied Mathematics and Computer Science, 30(2), 325–336.
Hamid, K., Asif, A., Abbasi, W., Sabih, D., & Afsar, F. A. (2017). Machine learning with abstention for
automated liver disease diagnosis. In 2017 international conference on frontiers of information technology (FIT), (vol. 2017-Jan, pp. 356–361). IEEE.
Hanczar, B. (2019). Performance visualization spaces for classification with rejection option. Pattern Recognition, 96, 106984.
Hanczar, B., & Dougherty, E. R. (2008). Classification with reject option in gene expression data. Bioinformatics, 24(17), 1889–1895.
Hanczar, B., & Sebag, M. (2014). Combination of one-class support vector machines for classification with
reject option. Machine Learning and Knowledge Discovery in Databases - Part I (pp. 547–562).
Springer.
Hansen, L. K., Liisberg, C., & Salamon, P. (1997). The error-reject tradeoff. Open Systems & Information
Dynamics, 4(2), 159–184.
Hatami, N., & Chira, C. (2013). Classifiers with a reject option for early time-series classification. Proceedings of the 2013 IEEE symposium on computational intelligence and ensemble learning, CIEL 2013
- 2013 IEEE symposium series on computational intelligence, SSCI 2013, (pp. 9–16).
Hellman, M. E. (1970). The nearest neighbor classification rule with a reject option. IEEE Transactions on
Systems Science and Cybernetics, 6(3), 179–185.
Hendrickx, K., Meert, W., Cornelis, B., & Davis, J. (2022). Know your limits: Machine learning with rejection for vehicle engineering. In Lecture notes in computer science (including subseries lecture notes
in artificial intelligence and lecture notes in bioinformatics), (vol. 13087 LNAI, pp. 273–288).

13

Machine Learning (2024) 113:3073–3110

3105

Heo, J., Lee, H. B., Kim, S., Lee, J., Kim, K. J., Yang, E., & Hwang, S. J. (2018). Uncertainty-aware
attention for reliable interpretation and prediction. In Advances in neural information processing
systems, (vol. 31, pp. 909–918), Montreal, Canada. Curran Associates, Inc.
Herbei, R., & Wegkamp, M. H. (2006). Classification with reject option. Canadian Journal of Statistics,
34(4), 709–721.
Homenda, W., Luckner, M., & Pedrycz, W. (2014). Classification with rejection based on various SVM
techniques. In 2014 International joint conference on neural networks (IJCNN), (pp. 3480–3487).
IEEE.
Homenda, W., Luckner, M., & Pedrycz, W. (2016). Classification with rejection: Concepts and evaluations. Advances in Intelligent Systems and Computing, 364(December), 413–425.
Hosseini, H., Chen, Y., Kannan, S., Zhang, B., & Poovendran, R. (2017). Blocking transferability of
adversarial examples in black-box learning systems. arXiv preprintarXiv:​1703.​04318.
Hsu, Y. C., Shen, Y., Jin, H., & Kira, Z. (2020). Generalized ODIN: Detecting out-of-distribution image
without learning from out-of-distribution data. In Proceedings of the IEEE computer society conference on computer vision and pattern recognition, (pp. 10948–10957).
Huang, L., Zhang, C., & Zhang, H. (2020). Self-adaptive training: Beyond empirical risk minimization.
Advances in neural information processing systems, 2020-Decem(NeurIPS), (pp. 1–12).
Huang, Y., & Suen, C. (1995). A method of combining multiple experts for the recognition of unconstrained handwritten numerals. IEEE Transactions on Pattern Analysis and Machine Intelligence,
17(1), 90–94.
Jiang, W., Zhao, Y., & Wang, Z. (2020). Risk-controlled selective prediction for regression deep neural
network models. In 2020 international joint conference on neural networks (IJCNN), (pp. 1–8).
IEEE.
Jigang, X., Zhengding, Q., & Jie, W. (2006). Bootstrap methods for reject rules of fisher LDA. Proceedings - International Conference on Pattern Recognition, 3, 425–428.
Kalai, A. T., & Kanade, V. (2021). Towards optimally abstaining from prediction with OOD test examples. Advances in Neural Information Processing Systems, 16(NeurIPS), 12774–12785.
Kang, S., Cho, S., Rhee, S.-J., & Yu, K.-S. (2017). Reliable prediction of anti-diabetic drug failure using
a reject option. Pattern Analysis and Applications, 20(3), 883–891.
Kato, M., Cui, Z., & Fukuhara, Y. (2020). ATRO: Adversarial training with a rejection option. 2019,
(pp. 1–18).
Khodra, M. L. (2016). Delegating classifiers for automatic text categorization delegating classifiers for
automatic text categorization (June).
Kocak, M. A., Ramirez, D., Erkip, E., & Shasha, D. (2020). SafePredict: A meta-algorithm for machine
learning that uses refusals to guarantee correctness. IEEE Transactions on Pattern Analysis and
Machine Intelligence, 43(2), 1.
Kompa, B., Snoek, J., & Beam, A. L. (2021). Second opinion needed: Communicating uncertainty in
medical machine learning. NPJ Digital Medicine, 4(1), 4.
Korycki, L., Cano, A., & Krawczyk, B. (2019). Active learning with abstaining classifiers for imbalanced drifting data streams. In 2019 IEEE international conference on big data (big data), (pp.
2334–2343). IEEE.
Kotelevskii, N., Artemenkov, A., Fedyanin, K., Noskov, F., Fishkov, A., Shelmanov, A., Vazhentsev, A.,
Petiushko, A., & Panov, M. (2022). Nonparametric uncertainty quantification for single deterministic neural network. (NeurIPS 2022), (pp. 1–16).
Kotropoulos, C., & Arce, G. R. (2009). Linear classifier with reject option for the detection of vocal fold
paralysis and vocal fold edema. Eurasip Journal on Advances in Signal Processing, 2009.
Krawczyk, B., & Cano, A. (2018). Online ensemble learning with abstaining classifiers for drifting and
noisy data streams. Applied Soft Computing, 68, 677–692.
Kühne, J., März, C., & Gühmann, C. (2021). Securing deep learning models with autoencoder based
anomaly detection. In Proceedings of the European conference of the PHM society 2021, (pp.
221–233), Virtual event. PHM Society.
Kummert, J., Paassen, B., Jensen, J., Gopfert, C., & Hammer, B. (2016). Local reject option for deterministic multi-class SVM. In Artificial neural networks and machine learning–ICANN 2016: 25th
international conference on artificial neural networks, Barcelona, Spain, September 6-9, 2016,
Proceedings, Part II 25, (pp. 251–258), Springer.
Kwok, J. T. (1999). Moderating the outputs of support vector machine classifiers. IEEE Transactions on
Neural Networks, 10(5), 1018–1031.
Lam, L., & Suen, C. Y. (1995). Optimal combinations of pattern classifiers. Pattern Recognition Letters,
16(9), 945–954.

13

3106

Machine Learning (2024) 113:3073–3110

Landgrebe, T. C., Tax, D. M., Paclík, P., & Duin, R. P. (2006). The interaction between classification and
reject performance for distance-based reject-option classifiers. Pattern Recognition Letters, 27(8),
908–917.
Landgrebe, T. C., Tax, D. M., Paclík, P., Duin, R. P., & Andrew, C. (2004). A combining strategy for illdefined problems. In Proceedings of the 15th annual symposium of the pattern recognition association of South Africa, (pp. 57–62).
Laroui, S., Descombes, X., Vernay, A., Villiers, F., Debreuve, E., Laroui, S., Descombes, X., Vernay, A.,
Villiers, F., Villalba, F., & Laroui, S. (2021). How to define a rejection class based on model learning? In 25th international conference on pattern recogniton, Milano.
Le Capitaine, H., & Frélicot, C. (2012). A family of measures for best top-n class-selective decision rules.
Pattern Recognition, 45(1), 552–562.
Lee, J. K., Bu, Y., Rajan, D., Sattigeri, P., Panda, R., Das, S., & Wornell, G. W. (2021). Fair selective classification via sufficiency. In Proceedings of the 38th international conference on machine learning,
(vol. 139, pp. 6076–6086).
Lei, J. (2014). Classification with confidence. Biometrika, 101(4), 755–769.
Lewicke, A., Sazonov, E. S., Corwin, M., Neuman, M., & Schuckers, S. (2008). Sleep versus wake classification from heart rate variability using computational intelligence: Consideration of rejection in
classification models. IEEE Transactions on Biomedical Engineering, 55(1), 108–118.
Li, M., & Sethi, I. K. (2006). Confidence-based classifier design. Pattern Recognition, 39(7), 1230–1240.
Lin, D., Sun, L., Toh, K. A., Zhang, J. B., & Lin, Z. (2018). Twin SVM with a reject option through ROC
curve. Journal of the Franklin Institute, 355(4), 1710–1732.
Lin, Z., Glass, L., Westover, M. B., Xiao, C., & Sun, J. (2022). SCRIB: Set-Classifier with class-specific
risk bounds for blackbox models. Proceedings of the AAAI Conference on Artificial Intelligence,
36(7), 7497–7505.
Liu, J., Gallego, B., & Barbieri, S. (2022). Incorporating uncertainty in learning to defer algorithms for safe
computer-aided diagnosis. Scientific Reports, 12(1), 1–9.
Loeffel, P. X., Marsala, C., & Detyniecki, M. (2015). Classification with a reject option under Concept
Drift: The Droplets algorithm. In Proceedings of the 2015 IEEE international conference on data science and advanced analytics, DSAA 2015, (pp. 1–9).
Lotte, F., Mouchère, H., & Lécuyer, A. (2008). Pattern rejection strategies for the design of self-paced EEGbased brain-computer interfaces. Proceedings - international conference on pattern recognition, (pp.
6–10).
Lou, Z., Liu, K., Yang, J., & Suen, C. (1999). Rejection criteria and pairwise discrimination of handwritten
numerals based on structural features. Pattern Analysis and Applications, 2(3), 228–238.
Ma, C., Randolph, M. A., & Drish, J. (2001). A support vector machines-based rejection technique for
speech recognition. ICASSP, IEEE International Conference on Acoustics, Speech and Signal Processing - Proceedings, 1, 381–384.
Madras, D., Pitassi, T., & Zemel, R. (2018). Predict responsibly: Improving fairness and accuracy by learning to defer. Advances in Neural Information Processing Systems, 2018(NeurIPS), 6147–6157.
Markou, M., & Singh, S. (2003). Novelty detection: A review-part 1: Statistical approaches. Signal Processing, 83(12), 2481–2497.
Marrocco, C., Molinara, M., & Tortorella, F. (2007). An empirical comparison of ideal and empirical ROCbased reject rules. Lecture notes in computer science, volume 4571 LNAI (pp. 47–60). Springer.
Martens, T., Perini, L., & Davis, J. (2023). Semi-supervised learning from active noisy soft labels for anomaly detection. In Joint European conference on machine learning and knowledge discovery in databases. Springer.
Mena, J., Pujol, O., & Vitria, J. (2020). Uncertainty-based rejection wrappers for black-box classifiers. IEEE
Access, 8, 101721–101746.
Mesquita, D. P., Rocha, L. S., Gomes, J. P. P., & da Rocha Neto, A. R. (2016). Classification with reject
option for software defect prediction. Applied Soft Computing Journal, 49, 1085–1093.
Mozannar, H., & Sontag, D. (2020). Consistent estimators for learning to defer to an expert. arXiv preprintarXiv:​2006.​01862.
Muzzolini, R., Yang, Y.-H., & Pierson, R. (1998). Classifier design with incomplete knowledge. Pattern
Recognition, 31(4), 345–369.
Nadeem, M. S. A., Zucker, J., & Hanczar, B. (2010). Accuracy-rejection curves (ARCs) for comparing classification methods with a reject option. Machine Learning in Systems Biology, 8, 65–81.
Nalisnick, E., Matsukawa, A., Whye, Y., Dilan, T., & Balaji, G. (2019). Hybrid models with deep and
invertible features (ICML, 2019).
Nguyen, V.-L., Destercke, S., & Hüllermeier, E. (2019). Epistemic uncertainty sampling. In International
conference on discovery science DS 2019, volume 11828 LNAI, (pp. 72–86). Springer.

13

Machine Learning (2024) 113:3073–3110

3107

Nguyen, V. L., & Hüllermeier, E. (2020). Reliable multilabel classification: Prediction with partial abstention. In AAAI 2020 - 34th AAAI conference on artificial intelligence, (vol. 34, pp. 5264–5271).
Nguyen, V. L., & Hüllermeier, E. (2021). Multilabel classification with partial Abstention: Bayes-optimal
prediction under label independence. Journal of Artificial Intelligence Research, 72, 613–665.
Ni, C., Charoenphakdee, N., Honda, J., & Sugiyama, M. (2019). On the calibration of multiclass classification with rejection, (pp. 1–31). arXiv preprintarXiv:​1901.​10655
Pang, T., Zhang, H., He, D., Dong, Y., Su, H., Chen, W., Zhu, J., & Liu, T.-Y. (2021). Adversarial training
with rectified rejection, (pp. 1–23). arXiv preprintarXiv:​2105.​14785
Pang, T., Zhang, H., He, D., Dong, Y., Su, H., Chen, W., Zhu, J., & Liu, T. Y. (2022). Two coupled rejection
metrics can tell adversarial examples apart. In Proceedings of the IEEE computer society conference
on computer vision and pattern recognition, volume 2022-June, (pp. 15202–15212).
Pazzani, M. J., Murphy, P., Ali, K., & Schulenburg, D. (1994). Tradingoff coverage for accuracy in forecasts: Applications to clinical data analysis. In Proceedings of the AAAI symposium on AI in medicine, (pp. 100–104).
Perello-Nieto, M., Filho, T. M., Kull, M., & Flach, P. (2017). Background check: A general technique to
build more reliable and versatile classifiers. In Proceedings - IEEE international conference on data
mining, ICDM, (pp. 1143–1148).
Perini, L., Buerkner, P., & Klami, A. (2022a). Estimating the contamination factor’s distribution in unsupervised anomaly detection. In International conference on machine learning (ICML 2023).
Perini, L., Galvin, C., & Vercruyssen, V. (2020). A Ranking stability measure for quantifying the robustness of anomaly detection methods. Communications in Computer and Information Science, 1323,
397–408.
Perini, L., Giannuzzi, D., & Davis, J. (2023). How to allocate your label budget? Choosing between active
learning and learning to reject in anomaly detection. (1).
Perini, L., Vercruyssen, V., & Davis, J. (2020b). Quantifying the confidence of anomaly detectors in their
example-wise predictions. In Proceedings of European conference on machine learning and principles and practice of knowledge discovery in databases, Ghent, Belgium. ECML-PKDD.
Perini, L., Vercruyssen, V., & Davis, J. (2022b). Transferring the contamination factor between anomaly
detection domains by shape similarity. In Proceedings of the 36th AAAI conference on artificial intelligence, AAAI 2022, (vol. 36, pp. 4128–4136).
Pietraszek, T. (2005). Optimizing abstaining classifiers using ROC analysis. In Proceedings of the 22nd
international conference on Machine learning - ICML ’05, (pp. 665–672), New York, New York,
USA. ACM Press.
Pietraszek, T. (2007). On the use of ROC analysis for the optimization of abstaining classifiers. Machine
Learning, 68(2), 137–169.
Pillai, I., Fumera, G., & Roli, F. (2011). A classification approach with a reject option for multi-label problems. In Lecture notes in computer science, volume 6978 LNCS, (pp. 98–107). Springer.
Pillai, I., Fumera, G., & Roli, F. (2013). Multi-label classification with a reject option. Pattern Recognition,
46(8), 2256–2266.
Pimentel, M. A., Clifton, D. A., Clifton, L., & Tarassenko, L. (2014). A review of novelty detection. Signal
Processing, 99, 215–249.
Prasad, M., & Sowmya, A. (2008). Multi-level classification of emphysema in HRCT lung images using
delegated classifiers. Lecture notes in computer science (including subseries lecture notes in artificial
intelligence and lecture notes in bioinformatics), 5241 LNCS(PART 1), 59–66.
Prasad, N. R., Almanza-Garcia, S., & Lu, T. T. (2009). Anomaly detection. Computers, Materials and Continua, 14(1), 1–22.
Puchkin, N., & Zhivotovskiy, N. (2022). Exponential savings in agnostic active learning through abstention.
IEEE Transactions on Information Theory, 68(7), 4651–4665.
Pudil, P., Novovičova, J., Bláha, S., & Kittler, J. (1992). Multistage pattern recognition with reject option. In
Proceedings - international conference on pattern recognition, (Vol. 2, pp. 92–95).
Pugnana, A., & Ruggieri, S. (2022). AUC-based selective classification. In International conference on artificial intelligence and statistics, 206.
Pugnana, A., & Ruggieri, S. (2023). A model-agnostic heuristics for selective classification. Proceedings of
the AAAI Conference on Artificial Intelligence, 37(8), 9461–9469.
Rahman, A., & Fairhurst, M. (1998). An evaluation of multi-expert configurations for the recognition of
handwritten numerals. Pattern Recognition, 31(9), 1255–1273.
Ramaswamy, H. G., Tewari, A., & Agarwal, S. (2018). Consistent algorithms for multiclass classification
with an abstain option. Electronic Journal of Statistics, 12(1), 530–554.
Ruggieri, S., Alvarez, J. M., Pugnana, A., State, L., & Turini, F. (2023). Can We Trust Fair-AI ? AAAI 2023.

13

3108

Machine Learning (2024) 113:3073–3110

Sambu Seo, Wallat, M., Graepel, T., & Obermayer, K. (2000). Gaussian process regression: Active data
selection and test point rejection. In Proceedings of the IEEE-INNS-ENNS international joint conference on neural networks. IJCNN 2000. Neural computing: New challenges and perspectives for
the New Millennium, (Vol. 3, pp. 241–246). IEEE.
Sansone, C., Tortorella, F., & Vento, M. (2001). A classification reliability driven reject rule for multiexpert systems. International Journal of Pattern Recognition and Artificial Intelligence, 15(06),
885–904.
Santos-Pereira, C. M., & Pires, A. M. (2005). On optimal reject rules and ROC curves. Pattern Recognition Letters, 26(7), 943–952.
Sayedi, A., Zadimoghaddam, M., & Blum, A. (2010). Trading off mistakes and don’t-know predictions.
Advances in neural information processing systems 23: 24th annual conference on neural information processing systems 2010, NIPS 2010, (pp. 1–9).
Senge, R., Bösner, S., Dembczyński, K., Haasenritter, J., Hirsch, O., Donner-Banzhoff, N., & Hüllermeier, E. (2014). Reliable classification: Learning classifiers that distinguish aleatoric and epistemic uncertainty. Information Sciences, 255, 16–29.
Settles, B. (2009). Active learning literature survey.
Sharma, M., & Bilgic, M. (2017). Evidence-based uncertainty sampling for active learning. Data Mining
and Knowledge Discovery, 31(1), 164–202.
Shekhar, S., Ghavamzadeh, M., & Javidi, T. (2019). Binary classification with bounded abstention rate,
(pp. 1–35). arXiv preprintarXiv:​1905.​09561
Shekhar, S., Ghavamzadeh, M., & Javidi, T. (2020). Active learning for classification with abstention. In
IEEE International Symposium on Information Theory - Proceedings, 2020-June(2), 2801–2806.
Shen, S. Q., Yang, B. B., & Gao, W. (2020a). AUC optimization with a reject option. In AAAI 2020 34th AAAI conference on artificial intelligence, (pp. 5686–5691).
Shen, Z., Chen, X., & Garibaldi, J. M. (2020b). A novel meta learning framework for feature selection using data synthesis and fuzzy similarity. In IEEE international conference on fuzzy systems,
2020-July.
Shpakova, T., & Sokolovska, N. (2021). Probabilistic personalised cascade with abstention. Pattern Recognition Letters, 147, 8–15.
Singh, S., & Markou, M. (2004). An approach to novelty detection applied to the classification of image
regions. IEEE Transactions on Knowledge and Data Engineering, 16(4), 396–407.
Sotgiu, A., Demontis, A., Melis, M., Biggio, B., Fumera, G., Feng, X., & Roli, F. (2020). Deep neural
rejection against adversarial examples. EURASIP Journal on Information Security, 2020(1), 5.
Suutala, J., Pirttikangas, S., Riekki, J., & Röning, J. (2004). Reject-optional LVQ-based two-level classifier to improve reliability in footstep identification. In Lecture notes in computer science, (vol.
3001, pp. 182–187). Springer.
Tang, W., & Sazonov, E. S. (2014). Highly accurate recognition of human postures and activities through
classification with rejection. IEEE Journal of Biomedical and Health Informatics, 18(1), 309–315.
Tax, D. M., & Duin, R. P. (2008). Growing a multi-class classifier with a reject option. Pattern Recognition Letters, 29(10), 1565–1570.
Temanni, M.-r., & Nadeem, S. A. (2007). Aggregating Abstaining and Delegating Classifiers For
Improving Classification performance: An application to lung cancer survival prediction. Camda
07, (January 2017).
Thulasidasan, S., Bhattacharya, T., Bilmes, J., Chennupati, G., & Mohd-Yusof, J. (2019). Combating
label noise in deep learning using abstention. In Proceedings of the 36th international conference
on machine learning.
Tortorella, F. (2000). An optimal reject rule for binary classifiers. In Lecture notes in computer science,
vol. 1876 LNCS, (pp. 611–620). Springer.
Tremmel, C., Fernandez-Vargas, J., Stamos, D., Cinel, C., Pontil, M., Citi, L., & Poli, R. (2022). A metalearning BCI for estimating decision confidence. Journal of Neural Engineering, 19(4).
Ulmer, D., & Cinà, G. (2020). Know your limits: Uncertainty estimation with ReLU classifiers fails at
reliable OOD detection. arXiv preprintarXiv:​2012.​05329
Urahama, K., & Furukawa, Y. (1995). Gradient descent learning of nearest neighbor classifiers with outlier rejection. Pattern Recognition, 28(5), 761–768.
Vailaya, A., & Jain, A. (2000). Reject option for VQ-based Bayesian classification. In Proceedings 15th
international conference on pattern recognition. ICPR-2000, (vol. 2, pp. 48–51). IEEE Comput.
Soc.
Van Craenendonck, T., Meert, W., Dumančić, S., & Blockeel, H. (2018). COBRASTS: A new approach
to semi-supervised clustering of time series. Lecture notes in computer science (including

13

Machine Learning (2024) 113:3073–3110

3109

subseries lecture notes in artificial intelligence and lecture notes in bioinformatics), 11198 LNAI,
179–193.
Van der Plas, D., Meert, W., Verbraecken, J., & Davis, J. (2021). A reject option for automated sleep
stage scoring. In ICML workshop on interpretable machine learning in healthcare, Virtual event.
Van der Plas, D., Meert, W., Verbraecken, J., & Davis, J. (2023). A novel reject option applied to sleep
stage scoring. In Proceedings of the 2023 SIAM international conference on data mining (SDM),
pp. 820–828.
Vanderlooy, S., Sprinkhuizen-Kuyper, I., & Smirnov, E. (2006a). Reliable classifiers in ROC space. Proceedings of the 15th BENELEARN machine learning conference, p. 27.
Vanderlooy, S., Sprinkhuizen-Kuyper, I. G., & Smirnov, E. N. (2006b). An analysis of reliable classifiers
through ROC isometrics. ROC analysis in machine learning, (Citeseer).
Vanschoren, J. (2018). Meta-learning: A survey. pp. 1–29.
Varshney, K. R. (2006). A kernel based rejection method for supervised classification. International
Journal of Computational Intelligence, 3(4), 312–321.
Varshney, K. R. (2011). A risk bound for ensemble classification with a reject option. In 2011 IEEE statistical signal processing workshop (SSP), (pp. 769–772). IEEE.
Vasconcelos, G., Fairhurst, M., & Bisset, D. (1993). Enhanced reliability of multilayer perceptron networks through controlled pattern rejection. Electronics Letters, 29(3), 261.
Vasconcelos, G., Fairhurst, M., & Bisset, D. (1995). Investigating feedforward neural networks with
respect to the rejection of spurious patterns. Pattern Recognition Letters, 16(2), 207–212.
Vercruyssen, V., Meert, W., Verbruggen, G., Maes, K., Baumer, R., & Davis, J. (2018). Semi-supervised
anomaly detection with an application to water analytics. Proceedings - IEEE international conference on data mining, ICDM, 2018-Nov, (pp. 527–536).
Villmann, T., Kaden, M., Nebel, D., & Biehl, M. (2015). Learning vector quantization with adaptive
cost-based outlier-rejection. In Lecture notes in computer science, (vol. 9257, pp. 772–782).
Springer.
Wang, X., & Yiu, S. M. (2020). Classification with rejection: Scaling generative classifiers with supervised deep infomax. In Proceedings of the twenty-ninth international joint conference on artificial
intelligence, (pp. 2980–2986), California. International joint conferences on artificial intelligence
organization.
Wegkamp, M. H. (2007). Lasso type classifiers with a reject option. Electronic Journal of Statistics, 1,
155–168.
Wegkamp, M. H., & Yuan, M. (2012). Support vector machines with a reject option. Bernoulli, 17(4),
1368–1385.
Wu, Q., Jia, C., & Chen, W. (2007). A novel classification-rejection sphere SVMs for multi-class classification problems. In Third international conference on natural computation (ICNC 2007), (vol. 1,
pp. 34–38). IEEE.
Xu, L., Krzyzak, A., Suen, C. Y. C., Krzyżak, A., & Suen, C. Y. C. (1992). Methods of combining multiple classifiers and their applications to handwriting recognition. IEEE Transactions on Systems,
Man, and Cybernetics, 22(3), 418–435.
Yuan, M., & Wegkamp, M. H. (2010). Classification methods with reject option based on convex risk
minimization. Journal of Machine Learning Research, 11, 111–130.
Zhang, B. (2013). Reliable classification of vehicle types based on cascade classifier ensembles. IEEE
Transactions on Intelligent Transportation Systems, 14(1), 322–332.
Zhang, C., & Chaudhuri, K. (2014). Beyond disagreement-based agnostic active learning. Advances in
Neural Information Processing Systems, 1(January), 442–450.
Zhang, C., Wang, W., & Qiao, X. (2018). On reject and refine options in multicategory classification.
Journal of the American Statistical Association, 113(522), 730–745.
Zhang, R., & Metaxas, D. (2006). RO-SVM: Support vector machine with reject option for image categorization. In Procedings of the British machine vision conference 2006, (pp. 1–123). British
Machine Vision Association.
Zheng, E.-H., Zou, C., Sun, J., & Chen, L. (2011). Cost-sensitive SVM with error cost and class-dependent reject cost. International Journal of Computer Theory and Engineering, 3(1), 130–135.
Zhou, L., Martínez-Plumed, F., Hernández-Orallo, J., Ferri, C., & Schellaert, W. (2022). Reject before
you run: Small assessors anticipate big language models. In CEUR workshop proceedings, (vol.
3169).
Zidelmal, Z., Amirou, A., & Belouchrani, A. (2012). Heartbeat classifcation using support vector
machines (SVMs) with an embedded reject option. International Journal of Pattern Recognition
and Artificial Intelligence, 26(01), 1250001.

13

Machine Learning (2024) 113:3073–3110

3110

Ziyin, L., Wang, Z. T., Liang, P. P., Salakhutdinov, R., Morency, L. P., & Ueda, M. (2019). Deep gamblers: Learning to abstain with portfolio theory. Advances in Neural Information Processing Systems, 32(NeurIPS), 1–17.
Zong, W., Huang, G. B., & Chen, Y. (2013). Weighted extreme learning machine for imbalance learning.
Neurocomputing, 101, 229–242.
Zou, C., Zheng, E.-H., Xu, H.-W., & Chen, L. (2011). Cost-sensitive multi-class SVM with reject option:
A method for steam turbine generator fault diagnosis. International Journal of Computer Theory and
Engineering, 3(1), 77–83.
Springer Nature or its licensor (e.g. a society or other partner) holds exclusive rights to this article under
a publishing agreement with the author(s) or other rightsholder(s); author self-archiving of the accepted
manuscript version of this article is solely governed by the terms of such publishing agreement and applicable
law.

Authors and Affiliations
Kilian Hendrickx1,2
Jesse Davis5

· Lorenzo Perini2 · Dries Van der Plas2,3,4 · Wannes Meert5 ·

* Kilian Hendrickx
kilian.hendrickx@cs.kuleuven.be
Lorenzo Perini
lorenzo.perini@cs.kuleuven.be
Dries Van der Plas
dries.vanderplas@cs.kuleuven.be
Wannes Meert
wannes.meert@cs.kuleuven.be
Jesse Davis
jesse.davis@cs.kuleuven.be
1

Siemens Digital Industries Software, Leuven, Belgium

2

Department of Computer Science, KU Leuven, Leuven, Belgium

3

OSG bv, Natus Medical, Kontich, Belgium

4

University of Antwerp, Antwerp, Belgium

5

KU Leuven; Leuven.AI, Leuven, Belgium

13

