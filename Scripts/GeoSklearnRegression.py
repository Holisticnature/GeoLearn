# --------------------------------
# Name: GeosklearnRegression.py
# Purpose: This script is intended to allow ArcGIS users that have Scikit Learn installed in their python installation
# utilize sklearn regression with a dependent and a set of independent variables. Parameters for the tool alter
# certain regression parameters of various sklearn models. This is an example not intended for industry grade modeling.
# Functions assumptions and defaults.
# Current Owner: David Wasserman
# Last Modified: 4/5/2020
# Copyright:   (c) CoAdapt
# ArcGIS Version:   ArcGIS Pro/10.4
# Python Version:   3.5/2.7
# --------------------------------
# Copyright 2016 David J. Wasserman
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# --------------------------------
# Import Modules
import os, arcpy
import numpy as np
from scipy import stats
import glearnlib as gl

try:
    from sklearn import linear_model
    from sklearn import metrics
    from sklearn import feature_selection
    from sklearn.externals import joblib
    from sklearn.preprocessing import StandardScaler
except:
    arcpy.AddError("This library requires Sci-kit Learn installed in the ArcGIS Python Install."
                   " Might require installing pre-requisite libraries and software.")


# Function Definitions
@gl.arc_tool_report
def get_model(regression_type, module, alpha=1, normalize=False):
    """Returns the appropriate sklearn model based on a passed string. All regression models use the fit()
    method so this generalizes the function to every regression model in imported modules.
    This function uses reflection to get the appropriate linear regression class from the linear model
    module. If this is exposed to user code outside of ArcGIS for Desktop it is highly suggested users not have
    access to this parameter.
    Inputs: Strings with Regression Class Method, Sklearn Module, alpha if one is chosen, and normalize boolean."""
    module_dict = globals()[module]
    gl.arc_print("Using input feature class and selected variables to establish {0} "
                 "Regression Model.".format(str(regression_type)), True)
    regression_model = getattr(module_dict, regression_type)()
    try:
        regression_model.set_params(alpha=alpha)
    except:
        print("Did not set alpha in model...")
    try:
        regression_model.set_params(normalize=normalize)
    except:
        print("Did not set normalize in model...")
    return regression_model


@gl.arc_tool_report
def regression_summary(regression_model, dependent_array, predicted_values, regressor_names=[],
                       independents_array=np.array([])):
    """Generates a regression summary list that can be iterated through and reported. Requires the scikit learn
    model, dependent true values, predicted values, and optionally regressor names to zip with coefficients and
    the independent variable array to report the regressors F Scores and P Values. .
    Depends on scipy.stats, and the sklearn feature selection and metrics modules.
    :param - regression_model - scikit learn model
    :param - dependent_array - array of dependent variable values
    :param - predicted_values - predicted values to evaluate against
    :param - regressor_names - independent variable column names
    :param - independents_array - independent values"""
    model_evaluation_list = []
    model_evaluation_list.append("REGRESSION MODEL: {0}".format(str(regression_model)))
    model_evaluation_list.append("MODEL COEFFICENTS")
    if len(regressor_names) == len(regression_model.coef_):
        model_evaluation_list.append("  Regression Coefficents:  {0}".format(" + ".join("{0} * {1}".format(round
                                                                                                           (coef, 3),
                                                                                                           name) for
                                                                                        coef, name in list(
            zip(regression_model.coef_, regressor_names)))))
    else:
        model_evaluation_list.append("  Regression Coefficents:  {0}".format(str(regression_model.coef_)))
    model_evaluation_list.append("  Regression Intercept:    {0}".format(str(regression_model.intercept_)))
    model_evaluation_list.append("MODEL EVALUATION")
    model_evaluation_list.append("  Model Coefficent of Determination: {0}".format(
        metrics.r2_score(dependent_array, predicted_values)))
    model_evaluation_list.append("  Model Mean Squared Error:          {0}".format(
        metrics.mean_squared_error(dependent_array, predicted_values)))
    model_evaluation_list.append("  Model Mean Absolute Error:         {0}".format(
        metrics.mean_absolute_error(dependent_array, predicted_values)))
    model_evaluation_list.append("  Model Median Absolute Error:       {0}".format(
        metrics.median_absolute_error(dependent_array, predicted_values)))
    try:
        if independents_array.shape[0] == dependent_array.shape[0]:
            model_evaluation_list.append(("REGRESSOR SCORES"))
            f_regression_scores, p_values = feature_selection.f_regression(independents_array, dependent_array)
            if len(regressor_names) == len(p_values):
                model_evaluation_list.append(
                    "  Regressor F-Scores:     {0}".format(str(list(zip(regressor_names, f_regression_scores)))))
                model_evaluation_list.append(
                    "  Regressor P-Values:     {0}".format(str(list(zip(regressor_names, p_values)))))
            else:
                model_evaluation_list.append("  Regressor F-Scores:     {0}".format(str(f_regression_scores)))
                model_evaluation_list.append("  Regressor P-Values:     {0}".format(str(p_values)))

    except:
        pass
    return model_evaluation_list


# Function Definitions
def feature_class_sklearn_regression(in_fc, regression_model_type, dependent_var, independent_vars,
                                     alpha=1, normalize=False, output_dir=None):
    """Take in a feature class and a selected dependent variable field and a set of independent variable fields to do
    cross-validated sklearn regression or sklearn regression with a chosen alpha. Predicted values will be extended to the
    feature class a output text file with model metrics will be output along with a pickled version of the model. """
    try:
        # Declare Starting Variables
        desc = arcpy.Describe(in_fc)
        OIDFieldName = desc.OIDFieldName
        workspace = os.path.dirname(desc.catalogPath)
        objectid = 'OID@'
        gl.arc_print("Converting '{0}' feature class fields to numpy arrays.".format(str(desc.name)))
        # Convert Feature Class to NP array
        dependent_geoarray = arcpy.da.FeatureClassToNumPyArray(in_fc, [objectid, dependent_var],
                                                               null_value=0)  # Null Values of treated as zero
        dependent_array = dependent_geoarray[dependent_var]
        oid_array = dependent_geoarray[objectid]
        independent_geoarray = arcpy.da.FeatureClassToNumPyArray(in_fc, independent_vars,
                                                                 null_value=0)  # Null Values of treated as zero
        # Record/Structured arrays returned by Arcpy are incompatible shapes-need to be coerced to appropriate view
        independent_array = independent_geoarray.view((np.float64, len(independent_geoarray.dtype.names)))

        regression_model = get_model(regression_model_type, "linear_model", alpha=alpha, normalize=normalize)

        gl.arc_print("Fitting {0} model to data.".format(regression_model), True)
        regression_model.fit(independent_array, dependent_array)
        predicted_values = regression_model.predict(independent_array)
        JoinField = str(arcpy.ValidateFieldName("NPIndexJoin", workspace))
        PredictedField = str(arcpy.ValidateFieldName("PredictedValues", workspace))

        final_predicted_array = np.array(list(zip(oid_array, predicted_values)),
                                         dtype=[(JoinField, np.int32), (PredictedField, np.float64)])
        gl.arc_print("Extending Prediction Fields to Output Feature Class.",
                     True)
        arcpy.da.ExtendTable(in_fc, OIDFieldName, final_predicted_array, JoinField, append_only=False)

        regession_report = regression_summary(regression_model, dependent_array, predicted_values, independent_vars,
                                              independent_array)
        valid_output_file_directory = os.path.isdir(output_dir)
        if valid_output_file_directory:
            gl.arc_print("Outputing Report and Pickled model to valid directory.", True)
            report_name = "{0}_Report.txt".format(regression_model_type)
            # Will update if report exists.
            text_report = open(os.path.join(output_dir, report_name), "w")
            model_name = "{0}_Model.pkl".format(regression_model_type)
            model_path = os.path.join(output_dir, model_name)
            if os.path.exists(model_path):
                os.remove(model_path)
            joblib.dump(regression_model, model_path)
        for report in regession_report:
            gl.arc_print(report)
            if valid_output_file_directory:
                text_report.write(str(report) + "\n")

        del dependent_geoarray, independent_array
        gl.arc_print("Script Completed Successfully.", True)
    except arcpy.ExecuteError:
        gl.arc_print(arcpy.GetMessages(2))
    except Exception as e:
        gl.arc_print(e.args[0])


# End do_analysis function

# This test allows the script to be used from the operating
# system command prompt (stand-alone), in a Python IDE,
# as a geoprocessing script tool, or as a module imported in
# another script
if __name__ == '__main__':
    # Define input parameters

    input_feature_class = arcpy.GetParameterAsText(0)
    regression_model_choice = arcpy.GetParameterAsText(1)
    dependent_var = arcpy.GetParameterAsText(2)
    independent_vars = [str(i) for i in str(arcpy.GetParameterAsText(3)).split(";")]
    alpha = arcpy.GetParameter(4)
    normalize = arcpy.GetParameter(5)
    output_text_report = arcpy.GetParameterAsText(6)
    feature_class_sklearn_regression(input_feature_class, regression_model_choice, dependent_var, independent_vars,
                                     alpha, normalize, output_text_report)
