-- MySQL dump 10.13  Distrib 8.0.41, for Win64 (x86_64)
--
-- Host: localhost    Database: spps_db
-- ------------------------------------------------------
-- Server version	8.0.41

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('7ab2590aa8d0');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `institution`
--

DROP TABLE IF EXISTS `institution`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `institution` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `institution`
--

LOCK TABLES `institution` WRITE;
/*!40000 ALTER TABLE `institution` DISABLE KEYS */;
INSERT INTO `institution` VALUES (1,'? GOVT. POLYTECHNIC, SIDDIPET');
/*!40000 ALTER TABLE `institution` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `marks`
--

DROP TABLE IF EXISTS `marks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `marks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `student_id` int NOT NULL,
  `sub_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `mid1` float DEFAULT NULL,
  `mid2` float DEFAULT NULL,
  `internal` float DEFAULT NULL,
  `end_sem` float DEFAULT NULL,
  `attendance` float DEFAULT NULL,
  `total` float DEFAULT NULL,
  `semester` int NOT NULL,
  `year` int NOT NULL,
  `subject_score` float DEFAULT NULL,
  `risk` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_on` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uix_student_subject_sem` (`student_id`,`sub_code`,`semester`),
  KEY `sub_code` (`sub_code`),
  CONSTRAINT `marks_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`),
  CONSTRAINT `marks_ibfk_2` FOREIGN KEY (`sub_code`) REFERENCES `subjects` (`sub_code`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `marks`
--

LOCK TABLES `marks` WRITE;
/*!40000 ALTER TABLE `marks` DISABLE KEYS */;
INSERT INTO `marks` VALUES (1,1,'CS-401',15,18,16,38,85,87,4,2024,87.25,'low','2025-09-14 07:07:06'),(2,7,'SC-401',2,8,15,1,NULL,26,4,2024,26.11,'high','2025-09-14 13:57:57'),(3,7,'CS-402',15,8,17,29,NULL,69,4,2024,70.28,'low','2025-09-14 13:57:57'),(4,7,'CS-403',16,15,16,5,NULL,52,4,2024,49.17,'high','2025-09-14 13:57:57'),(5,7,'CS-404',5,9,17,9,NULL,40,4,2024,40.56,'high','2025-09-14 13:57:57'),(6,7,'CS-405',11,14,17,30,NULL,72,4,2024,73.06,'low','2025-09-14 13:57:57'),(7,7,'CS-406',18,18,17,37,NULL,90,4,2024,90,'low','2025-09-14 13:57:57'),(8,7,'CS-407',14,13,16,35,NULL,78,4,2024,79.17,'low','2025-09-14 13:57:57'),(9,7,'CS-408',17,17,17,36,NULL,87,4,2024,87.22,'low','2025-09-14 13:57:57'),(10,7,'CS-409',18,18,17,37,NULL,90,4,2024,90,'low','2025-09-14 13:57:57'),(11,7,'HU-410',16,16,16,36,NULL,84,4,2024,84.44,'low','2025-09-14 13:57:57');
/*!40000 ALTER TABLE `marks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `students`
--

DROP TABLE IF EXISTS `students`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `students` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pin` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `branch` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `exam_year` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `pin` (`pin`)
) ENGINE=InnoDB AUTO_INCREMENT=71 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `students`
--

LOCK TABLES `students` WRITE;
/*!40000 ALTER TABLE `students` DISABLE KEYS */;
INSERT INTO `students` VALUES (1,'23189-CS-001','Student-1','CS',2024),(2,'College Code','College Name','CS',2024),(3,'189','GOVT.POLYTECHNIC,SIDDIPET','CS',2024),(4,'Scheme','Sem & Year','CS',2024),(5,'C21','4SEM','CS',2024),(6,'Pin','Name','CS',2024),(7,'','','CS',2024),(8,'23189-CS-002','Srudent-2','CS',2024),(9,'23189-CS-003','Srudent-3','CS',2024),(10,'23189-CS-004','Srudent-4','CS',2024),(11,'23189-CS-005','Srudent-5','CS',2024),(12,'23189-CS-006','Srudent-6','CS',2024),(13,'23189-CS-007','Srudent-7','CS',2024),(14,'23189-CS-008','Srudent-8','CS',2024),(15,'23189-CS-009','Srudent-9','CS',2024),(16,'23189-CS-010','Srudent-10','CS',2024),(17,'23189-CS-011','Srudent-11','CS',2024),(18,'23189-CS-012','Srudent-12','CS',2024),(19,'23189-CS-013','Srudent-13','CS',2024),(20,'23189-CS-014','Srudent-14','CS',2024),(21,'23189-CS-015','Srudent-15','CS',2024),(22,'23189-CS-016','Srudent-16','CS',2024),(23,'23189-CS-017','Srudent-17','CS',2024),(24,'23189-CS-018','Srudent-18','CS',2024),(25,'23189-CS-019','Srudent-19','CS',2024),(26,'23189-CS-020','Srudent-20','CS',2024),(27,'23189-CS-021','Srudent-21','CS',2024),(28,'23189-CS-022','Srudent-22','CS',2024),(29,'23189-CS-023','Srudent-23','CS',2024),(30,'23189-CS-024','Srudent-24','CS',2024),(31,'23189-CS-025','Srudent-25','CS',2024),(32,'23189-CS-026','Srudent-26','CS',2024),(33,'23189-CS-028','Srudent-27','CS',2024),(34,'23189-CS-029','Srudent-28','CS',2024),(35,'23189-CS-030','Srudent-29','CS',2024),(36,'23189-CS-032','Srudent-30','CS',2024),(37,'23189-CS-033','Srudent-31','CS',2024),(38,'23189-CS-034','Srudent-32','CS',2024),(39,'23189-CS-035','Srudent-33','CS',2024),(40,'23189-CS-036','Srudent-34','CS',2024),(41,'23189-CS-037','Srudent-35','CS',2024),(42,'23189-CS-038','Srudent-36','CS',2024),(43,'23189-CS-039','Srudent-37','CS',2024),(44,'23189-CS-040','Srudent-38','CS',2024),(45,'23189-CS-041','Srudent-39','CS',2024),(46,'23189-CS-042','Srudent-40','CS',2024),(47,'23189-CS-043','Srudent-41','CS',2024),(48,'23189-CS-045','Srudent-42','CS',2024),(49,'23189-CS-046','Srudent-43','CS',2024),(50,'23189-CS-047','Srudent-44','CS',2024),(51,'23189-CS-048','Srudent-45','CS',2024),(52,'23189-CS-049','Srudent-46','CS',2024),(53,'23189-CS-050','Srudent-47','CS',2024),(54,'23189-CS-051','Srudent-48','CS',2024),(55,'23189-CS-052','Srudent-49','CS',2024),(56,'23189-CS-053','Srudent-50','CS',2024),(57,'23189-CS-054','Srudent-51','CS',2024),(58,'23189-CS-055','Srudent-52','CS',2024),(59,'23189-CS-056','Srudent-53','CS',2024),(60,'23189-CS-057','Srudent-54','CS',2024),(61,'23189-CS-058','Srudent-55','CS',2024),(62,'23189-CS-059','Srudent-56','CS',2024),(63,'23189-CS-060','Srudent-57','CS',2024),(64,'23189-CS-061','Srudent-58','CS',2024),(65,'23189-CS-062','Srudent-59','CS',2024),(66,'23189-CS-063','Srudent-60','CS',2024),(67,'23189-CS-064','Srudent-61','CS',2024),(68,'23189-CS-065','Srudent-62','CS',2024),(69,'23189-CS-066','Srudent-63','CS',2024),(70,'23189-CS-067','Srudent-64','CS',2024);
/*!40000 ALTER TABLE `students` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subjects`
--

DROP TABLE IF EXISTS `subjects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `subjects` (
  `sub_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sub_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `branch` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `year` int NOT NULL,
  `semester` int NOT NULL,
  PRIMARY KEY (`sub_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subjects`
--

LOCK TABLES `subjects` WRITE;
/*!40000 ALTER TABLE `subjects` DISABLE KEYS */;
INSERT INTO `subjects` VALUES ('CS-401','Maths IV','CS',2,4),('CS-402','Computer Networks','CS',2024,4),('CS-403','Operating Systems','CS',2024,4),('CS-404','Database Management Systems','CS',2024,4),('CS-405','Software Engineering','CS',2024,4),('CS-406','Theory of Computation','CS',2024,4),('CS-407','Compiler Design','CS',2024,4),('CS-408','Artificial Intelligence','CS',2024,4),('CS-409','Web Technologies','CS',2024,4),('HU-410','Professional Communication','CS',2024,4),('SC-401','Mathematics-IV','CS',2024,4);
/*!40000 ALTER TABLE `subjects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `uploaded_files`
--

DROP TABLE IF EXISTS `uploaded_files`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `uploaded_files` (
  `id` int NOT NULL AUTO_INCREMENT,
  `file_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `original_file_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `exam_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `uploaded_by` int NOT NULL,
  `uploaded_on` datetime DEFAULT NULL,
  `note` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `uploaded_by` (`uploaded_by`),
  CONSTRAINT `uploaded_files_ibfk_1` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `uploaded_files`
--

LOCK TABLES `uploaded_files` WRITE;
/*!40000 ALTER TABLE `uploaded_files` DISABLE KEYS */;
INSERT INTO `uploaded_files` VALUES (1,'4th_Sem_Semester','sem.xlsx','semester',1,'2025-09-14 07:47:17',NULL),(2,'4th_Sem_Semester','sem.xlsx','semester',1,'2025-09-14 07:48:45',NULL),(3,'4th_Sem_Semester','sem.xlsx','semester',1,'2025-09-14 07:54:06',NULL);
/*!40000 ALTER TABLE `uploaded_files` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'testfaculty','scrypt:32768:8:1$G4sZsflCZHLDaSlY$8e6c16f4c48c07f56abbed3cc40071efc98cb28b5f4da34c73b2c29734d5f485c203c93350f44bdee8c4b9e0cadfcb3eb8ca3fa6e854feaea6d8310393eeece6','faculty');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-09-21 13:22:38
