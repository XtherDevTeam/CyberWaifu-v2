import os
import time
import sqlite3
import threading
import multiprocessing
import dataProvider
import AIDubMiddlewareAPI
import typing
import json
import tools

class TaskManager():
    def __init__(self, DataProvider: dataProvider.DataProvider):
        self.dataProvider = DataProvider
        self.api = AIDubMiddlewareAPI.AIDubMiddlewareAPI(self.dataProvider.getGPTSoVITsMiddleware())
       
       
    def createTask(self, stages: dict[str, typing.Any], status: str = "pending", log: str = ""):
        # create task in database
        creationTime = tools.TimeProvider()
        self.dataProvider.db.query("insert into tasks (status, stagesDescription, log, creationTime) values (?,?,?,?)", (status, json.dumps(stages), log, creationTime))
        current_id = self.dataProvider.db.query("select max(id) as id from tasks", one=True)['id']
        return current_id
        
        
    def checkIfTaskExists(self, taskId: int):
        return self.dataProvider.db.query("select id from tasks where id = ?", (taskId,), one=True) is not None
        
        
    def updateTaskStatus(self, status: str, taskId: int):
        if not self.checkIfTaskExists(taskId):
            raise ValueError("Task with id {} does not exist".format(taskId))
        if status not in ["pending", "running", "completed", "failed"]:
            raise ValueError("Invalid status: {}".format(status))
        if status == "completed":
            self.dataProvider.db.query("update tasks set completionTime = ? where id = ?", (tools.TimeProvider(), taskId))
        self.dataProvider.db.query("update tasks set status = ? where id = ?", (status, taskId))
       
       
    def updateTaskLog(self, log: str, taskId: int):
        if not self.checkIfTaskExists(taskId):
            raise ValueError("Task with id {} does not exist".format(taskId))
        original_log = self.dataProvider.db.query("select log from tasks where id = ?", (taskId,), one=True)['log']
        log = original_log + "\n" + log
        self.dataProvider.db.query("update tasks set log = ? where id = ?", (log, taskId))
       
       
    def updateTaskStage(self, stage: int, taskId: int):
        if not self.checkIfTaskExists(taskId):
            raise ValueError("Task with id {} does not exist".format(taskId))
        stages = self.dataProvider.db.query("select stagesDescription from tasks where id = ?", (taskId,), one=True)['stagesDescription']
        stages = json.loads(stages)
        stages['current_stage'] = stage
        self.dataProvider.db.query("update tasks set stagesDescription = ? where id = ?", (json.dumps(stages), taskId))
 
    def runAIDubModelTraining(self, enabled_char_names: list[str] = [], sources_to_fetch: list[str] = []):
        # create task in database
        stages = {
            "current_stage": 0,
            "total_stages": [
                "Dataset download",
                "Emotion classification",
                "Preprocessing: Get text",
                "Preprocessing: Get hubert wav32k",
                "Preprocessing: Name to semantic",
                "Training: GPT",
                "Training: SoVITs"
            ]
        }
        cur_id = self.createTask(stages)
        def wrapper():
            # download dataset
            self.updateTaskStage(1, cur_id)
            self.updateTaskLog(f"Sending request to download dataset for {enabled_char_names}...", cur_id)
            try:
                data = self.api.download_dataset(enabled_char_names, sources_to_fetch)
                self.updateTaskLog(f"Dataset downloaded successfully: {data}", cur_id)
            except AIDubMiddlewareAPI.AIDubAPIError as e:
                self.updateTaskStatus("failed", cur_id)
                self.updateTaskLog(f"Failed to download dataset: {e}", cur_id)
                return
            
            # emotion classification
            self.updateTaskStage(2, cur_id)
            self.updateTaskLog(f"Sending request to classify emotions for {enabled_char_names}...", cur_id)
            try:
                data = self.api.emotion_classification()
                self.updateTaskLog(f"Emotion classification completed successfully: {data}", cur_id)
            except AIDubMiddlewareAPI.AIDubAPIError as e:
                self.updateTaskStatus("failed", cur_id)
                self.updateTaskLog(f"Failed to classify emotions: {e}", cur_id)
                return
            
            # preprocessing: get text
            self.updateTaskStage(3, cur_id)
            self.updateTaskLog(f"Sending request to get text for {enabled_char_names}...", cur_id)
            try:
                data = self.api.data_preprocessing_get_text()
                self.updateTaskLog(f"Text preprocessing completed successfully: {data}", cur_id)
            except AIDubMiddlewareAPI.AIDubAPIError as e:
                self.updateTaskStatus("failed", cur_id)
                self.updateTaskLog(f"Failed to preprocess text: {e}", cur_id)
                return
            
            # preprocessing: get hubert wav32k
            self.updateTaskStage(4, cur_id)
            self.updateTaskLog(f"Sending request to get hubert wav32k for {enabled_char_names}...", cur_id)
            try:
                data = self.api.data_preprocessing_get_hubert_wav32k()
                self.updateTaskLog(f"Hubert wav32k preprocessing completed successfully: {data}", cur_id)
            except AIDubMiddlewareAPI.AIDubAPIError as e:
                self.updateTaskStatus("failed", cur_id)
                self.updateTaskLog(f"Failed to preprocess hubert wav32k: {e}", cur_id)
                return
            
            # preprocessing: name to semantic
            self.updateTaskStage(5, cur_id)
            self.updateTaskLog(f"Sending request to name to semantic for {enabled_char_names}...", cur_id)
            try:
                data = self.api.data_preprocessing_name_to_semantic()
                self.updateTaskLog(f"Name to semantic preprocessing completed successfully: {data}", cur_id)
            except AIDubMiddlewareAPI.AIDubAPIError as e:
                self.updateTaskStatus("failed", cur_id)
                self.updateTaskLog(f"Failed to preprocess name to semantic: {e}", cur_id)
                return
            
            # training: GPT
            self.updateTaskStage(6, cur_id)
            self.updateTaskLog(f"Sending request to train GPT for {enabled_char_names}...", cur_id)
            try:
                data = self.api.train_model_gpt()
                self.updateTaskLog(f"GPT training completed successfully: {data}", cur_id)
            except AIDubMiddlewareAPI.AIDubAPIError as e:
                self.updateTaskStatus("failed", cur_id)
                self.updateTaskLog(f"Failed to train GPT: {e}", cur_id)
                return
            
            # training: SoVITs
            self.updateTaskStage(7, cur_id)
            self.updateTaskLog(f"Sending request to train SoVITs for {enabled_char_names}...", cur_id)
            try:
                data = self.api.train_model_sovits()
                self.updateTaskLog(f"SoVITs training completed successfully: {data}", cur_id)
            except AIDubMiddlewareAPI.AIDubAPIError as e:
                self.updateTaskStatus("failed", cur_id)
                self.updateTaskLog(f"Failed to train SoVITs: {e}", cur_id)
                return
            
            # task completed
            self.updateTaskStatus("completed", cur_id)
            self.updateTaskLog(f"Task completed successfully for {enabled_char_names}", cur_id)
            
        t = threading.Thread(target=wrapper)
        t.start()
        return cur_id
    
    def getTaskInfo(self, taskId: int):
        if not self.checkIfTaskExists(taskId):
            raise ValueError("Task with id {} does not exist".format(taskId))
        task = self.dataProvider.db.query("select * from tasks where id = ?", (taskId,), one=True)
        return task
    
    def getInfo(self):
        return self.api.info()
    

    def getTasks(self):
        tasks = self.dataProvider.db.query("select id, status, stagesDescription, creationTime, completionTime from tasks order by id desc")
        return tasks
    
    
    def updateURL(self, url: str):
        self.api.url = url
        
        
    def deleteTask(self, taskId: int):
        if not self.checkIfTaskExists(taskId):
            raise ValueError("Task with id {} does not exist".format(taskId))
        self.dataProvider.db.query("delete from tasks where id = ?", (taskId,))