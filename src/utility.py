import numpy as np
import pandas as pd
import pytz as pytz
import tensorflow as tf
import matplotlib.pyplot as plt
import csv
import math
import seaborn as sns
from statsmodels.tsa.stattools import adfuller
import matplotlib.dates as mdates



def inverseDataScaling(data, cmax, cmin):
    cdiff = cmax-cmin
    unscaledData = np.zeros_like(data)
    for i in range(data.shape[0]):
        unscaledData[i] = round(max(data[i]*cdiff + cmin, 0), 5)
    return unscaledData

def getDatesInLocalTimeZone(dateTime):
    global LOCAL_TIMEZONE
    dates = []
    fromZone = pytz.timezone("UTC")
    for i in range(0, len(dateTime), 24):
        day = pd.to_datetime(dateTime[i]).replace(tzinfo=fromZone)
        day = day.astimezone(LOCAL_TIMEZONE)
        dates.append(day)    
    return dates

def getAvgContributionBySource(dataset):
    contribution = {}
    for col in dataset.columns:
        if "frac" in col:
            avgContribution = np.mean(dataset[col].values)
            print(col, ": ", avgContribution)
            contribution[col[5:]] = avgContribution
    contribution = dict(sorted(contribution.items(), key=lambda item: item[1]))
    return contribution

def getScores(scaledActual, scaledPredicted, unscaledActual, unscaledPredicted):
    print("Actual data shape, Predicted data shape: ", scaledActual.shape, scaledPredicted.shape)
    mse = tf.keras.losses.MeanSquaredError()
    rmseScore = round(math.sqrt(mse(scaledActual, scaledPredicted)), 6)

    mape = tf.keras.losses.MeanAbsolutePercentageError()
    mapeTensor =  mape(unscaledActual, unscaledPredicted)
    mapeScore = mapeTensor.numpy()

    return rmseScore, mapeScore

def writeOutFuelForecastFile(outFileName, data, fuel):
    print("Writing to ", outFileName, "...")
    fields = ["datetime", fuel+"_actual", "avg_"+fuel+"_production_forecast"]
    
    # writing to csv file 
    with open(outFileName, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile)   
        # writing the fields 
        csvwriter.writerow(fields) 
        # writing the data rows 
        csvwriter.writerows(data)

def showPlots():
    plt.show()

def scaleDataset(trainData, valData, testData):
    # Scaling columns to range (0, 1)
    row, col = trainData.shape[0], trainData.shape[1]
    ftMin, ftMax = [], []
    for i in range(col):
        fmax= trainData[0, i]
        fmin = trainData[0, i]
        for j in range(len(trainData[:, i])):
            if(fmax < trainData[j, i]):
                fmax = trainData[j, i]
            if (fmin > trainData[j, i]):
                fmin = trainData[j, i]
        ftMin.append(fmin)
        ftMax.append(fmax)
        # print(fmax, fmin)

    for i in range(col):
        if((ftMax[i] - ftMin[i]) == 0):
            continue
        trainData[:, i] = (trainData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        valData[:, i] = (valData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        testData[:, i] = (testData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])

    return trainData, valData, testData, ftMin, ftMax

# Date time feature engineering
def addDateTimeFeatures(dataset, dateTime, startCol):
    dates = []
    hourList = []
    hourSin, hourCos = [], []
    monthList = []
    monthSin, monthCos = [], []
    weekendList = []
    columns = dataset.columns
    secInDay = 24 * 60 * 60 # Seconds in day 
    secInYear = year = (365.25) * secInDay # Seconds in year 

    day = pd.to_datetime(dateTime[0])
    isWeekend = 0
    zero = 0
    one = 0
    for i in range(0, len(dateTime)):
        day = pd.to_datetime(dateTime[i])
        dates.append(day)
        hourList.append(day.hour)
        hourSin.append(np.sin(day.hour * (2 * np.pi / 24)))
        hourCos.append(np.cos(day.hour * (2 * np.pi / 24)))
        monthList.append(day.month)
        monthSin.append(np.sin(day.timestamp() * (2 * np.pi / secInYear)))
        monthCos.append(np.cos(day.timestamp() * (2 * np.pi / secInYear)))
        if (day.weekday() < 5):
            isWeekend = 0
            zero +=1
        else:
            isWeekend = 1
            one +=1
        weekendList.append(isWeekend)        
    loc = startCol+1
    print(zero, one)
    # hour of day feature
    dataset.insert(loc=loc, column="hour_sin", value=hourSin)
    dataset.insert(loc=loc+1, column="hour_cos", value=hourCos)
    # month of year feature
    dataset.insert(loc=loc+2, column="month_sin", value=monthSin)
    dataset.insert(loc=loc+3, column="month_cos", value=monthCos)
    # is weekend feature
    dataset.insert(loc=loc+4, column="weekend", value=weekendList)

    # print(dataset.columns)
    print(dataset.head())
    return dataset

def splitDataset(dataset, testDataSize, valDataSize): # testDataSize, valDataSize are in days
    print("No. of rows in dataset:", len(dataset))
    valData = None
    numTestEntries = testDataSize * 24
    numValEntries = valDataSize * 24
    trainData, testData = dataset[:-numTestEntries], dataset[-numTestEntries:]
    fullTrainData = np.copy(trainData)
    trainData, valData = trainData[:-numValEntries], trainData[-numValEntries:]
    print("No. of rows in training set:", len(trainData))
    print("No. of rows in validation set:", len(valData))
    print("No. of rows in test set:", len(testData))
    return trainData, valData, testData, fullTrainData

def showModelSummary(history, model):
    print("Showing model summary...")
    model.summary()
    print("***** Model summary shown *****")
    # list all data in history
    print(history.history.keys()) # ['loss', 'mean_absolute_error', 'val_loss', 'val_mean_absolute_error']
    # fig = plt.figure()
    # subplt1 = fig.add_subplot(2, 1, 1)
    # subplt1.plot(history.history['mean_absolute_error'])
    # subplt1.plot(history.history['val_mean_absolute_error'])
    # subplt1.legend(['train MAE', 'val_MAE'], loc="upper left")
    # # summarize history for loss
    # subplt2 = fig.add_subplot(2, 1, 2)
    # subplt2.plot(history.history['loss'])
    # subplt2.plot(history.history['val_loss'])
    # subplt2.legend(['train RMSE', 'val RMSE'], loc="upper left")
    
    # # plt.plot(history.history["loss"])
    # # plt.xlabel('epoch')
    # # plt.ylabel("RMSE")
    # # plt.title('Training loss (RMSE)')
    return

def analyzeTimeSeries(dataset, trainData, unscaledCarbonIntensity, dateTime):
    global NUM_FEATURES
    global LOCAL_TIMEZONE
    global START_COL
    # checkStationarity(dataset)
    # showTrends(dataset, dateTime, LOCAL_TIMEZONE)
    print("Plotting each feature distribution...")
    features = dataset.columns.values[START_COL:START_COL+NUM_FEATURES]
    trainDataFrame = pd.DataFrame(unscaledCarbonIntensity, columns=features)
    createFeatureViolinGraph(features, trainDataFrame, dateTime)
    print("***** Feature distribution plotting done *****")
    return

def checkStationarity(dataset):
    print(dataset.columns)
    carbon = dataset["carbon_intensity"].values
    print(len(carbon))
    result = adfuller(carbon, autolag='AIC')
    print(f'ADF Statistic: {result[0]}')
    print(f'n_lags: {result[1]}')
    print(f'p-value: {result[1]}')
    for key, value in result[4].items():
        print('Critial Values:')
        print(f'   {key}, {value}')
    return

def showTrends(dataset, dateTime, localTimeZone):
    global MONTH_INTERVAL
    carbon = np.array(dataset["carbon_intensity"].values)
    carbon = np.resize(carbon, (carbon.shape[0]//24, 24))
    dailyAvgCarbon = np.mean(carbon, axis = 1)
    dates = getDatesInLocalTimeZone(dateTime)    
    
    fig, ax = plt.subplots()
    ax.plot(dates, dailyAvgCarbon)
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d, %H:%M"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=MONTH_INTERVAL, tz=localTimeZone))
    
    plt.xlabel("Local time")
    plt.ylabel("Carbon Intensity (g/kWh)")
    # plt.title("Carbon Intensity Trend")
    plt.grid(axis="x")
    plt.xticks(rotation=90)

    plt.legend()
    # plt.show()
    return

def createFeatureViolinGraph(features, dataset, dateTime):
    # print(features)
    # print(dataset)
    dataset = dataset.astype(np.float64)
    plt.figure() #figsize=(12, 6)
    datasetMod = dataset.melt(var_name='Column', value_name='Normalized values')
    ax = sns.violinplot(x='Column', y='Normalized values', data=datasetMod, scale="count")
    # ax = plt.boxplot(dataset, vert=True)
    # for ft in features:
    #     print(ft, np.amax(dataset[ft].values), np.amin(dataset[ft].values))
    _ = ax.set_xticklabels(features, rotation=80)
    plt.show()
    return

def getMape(dates, actual, forecast):
    avgDailyMape = []
    mape = tf.keras.losses.MeanAbsolutePercentageError()
    for i in range(0, len(actual), 24):
        mapeTensor =  mape(actual[i:i+24], forecast[i:i+24])
        mapeScore = mapeTensor.numpy()
        print("Day: ", dates[i], "MAPE: ", mapeScore)
        avgDailyMape.append(mapeScore)

    mapeTensor =  mape(actual, forecast)
    mapeScore = mapeTensor.numpy()
    return avgDailyMape, mapeScore