"""Uncertainty + decision lead's area: interval coverage and newsvendor staffing.

Input: any results/predictions/<model>.parquet with several quantiles.
Note: for a shortfall cost c_u and idle cost c_o the newsvendor staffing level
is the quantile at c_u / (c_u + c_o), e.g. 0.75 for a 3:1 ratio, so the model
must output (or let us interpolate) that quantile.
"""
