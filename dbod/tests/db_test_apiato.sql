DROP SCHEMA apiato CASCADE;
DROP SCHEMA apiato_ro CASCADE;
CREATE SCHEMA IF NOT EXISTS apiato;
CREATE SCHEMA IF NOT EXISTS apiato_ro;

------------------------------------------
-- TYPES
------------------------------------------
CREATE TYPE apiato.instance_state AS ENUM (
  'RUNNING',
  'MAINTENANCE',
  'AWATING-APPROVAL',
  'JOB-PENDING'
);

CREATE TYPE apiato.instance_status AS ENUM (
  'ACTIVE',
  'NON-ACTIVE'
);

CREATE TYPE apiato.instance_category AS ENUM (
  'PROD',
  'DEV',
  'TEST',
  'QA',
  'REF'
);

CREATE TYPE apiato.job_state AS ENUM (
  'FINISHED_FAIL',
  'FINISHED_OK'
);

------------------------------------------
-- LOV TABLES
------------------------------------------

--INSTANCE_TYPE
CREATE TABLE apiato.instance_type (
  instance_type_id serial,
  type             varchar(64) UNIQUE NOT NULL,
  description      varchar(1024),
  CONSTRAINT instance_type_pkey PRIMARY KEY (instance_type_id)
);

--VOLUME_TYPE
CREATE TABLE apiato.volume_type (
  volume_type_id   serial,
  type             varchar(64) UNIQUE NOT NULL,
  description      varchar(1024),
  CONSTRAINT volume_type_pkey PRIMARY KEY (volume_type_id)
);

------------------------------------------
-- TABLES
------------------------------------------
-- CLUSTER
CREATE TABLE apiato.cluster (
  cluster_id           serial,
  owner                varchar(32) NOT NULL,
  name                 varchar(128) UNIQUE NOT NULL,
  e_group              varchar(256),
  category             apiato.instance_category NOT NULL,
  creation_date        date NOT NULL,
  expiry_date          date,
  instance_type_id     int NOT NULL,
  project              varchar(128),
  description          varchar(1024),
  version              varchar(128),
  master_cluster_id    int,
  state                apiato.instance_state NOT NULL,
  status               apiato.instance_status NOT NULL,
  CONSTRAINT cluster_pkey               PRIMARY KEY (cluster_id),
  CONSTRAINT cluster_master_fk          FOREIGN KEY (master_cluster_id) REFERENCES apiato.cluster (cluster_id),
  CONSTRAINT cluster_instance_type_fk   FOREIGN KEY (instance_type_id)   REFERENCES apiato.instance_type (instance_type_id)
);
--FK INDEXES for CLUSTER table
CREATE INDEX cluster_master_idx ON apiato.cluster (master_cluster_id);
CREATE INDEX cluster_type_idx   ON apiato.cluster (instance_type_id);

-- HOST
CREATE TABLE apiato.host (
  host_id  serial,
  name     varchar(63) UNIQUE NOT NULL,
  memory   integer NOT NULL,
  CONSTRAINT host_pkey PRIMARY KEY (host_id)
);



-- INSTANCES
CREATE TABLE apiato.instance (
    instance_id          serial,
    owner                varchar(32) NOT NULL,
    name                 varchar(128) UNIQUE NOT NULL,
    e_group              varchar(256),
    category             apiato.instance_category NOT NULL,
    creation_date        date NOT NULL,
    expiry_date          date,
    instance_type_id     int NOT NULL,
    project              varchar(128),
    description          varchar(1024),
    version              varchar(128),
    master_instance_id   int,
    slave_instance_id    int,
    host_id              int,
    state                apiato.instance_state NOT NULL,
    status               apiato.instance_status NOT NULL,
    cluster_id           int,
    CONSTRAINT instance_pkey               PRIMARY KEY (instance_id),
    CONSTRAINT instance_master_fk          FOREIGN KEY (master_instance_id) REFERENCES apiato.instance (instance_id),
    CONSTRAINT instance_slave_fk           FOREIGN KEY (slave_instance_id)  REFERENCES apiato.instance (instance_id),
    CONSTRAINT instance_host_fk            FOREIGN KEY (host_id)            REFERENCES apiato.host     (host_id),
    CONSTRAINT instance_instance_type_fk   FOREIGN KEY (instance_type_id)   REFERENCES apiato.instance_type (instance_type_id),
    CONSTRAINT instance_cluster_fk         FOREIGN KEY (cluster_id)         REFERENCES apiato.cluster (cluster_id)
);
--FK INDEXES for INSTANCE table
CREATE INDEX instance_host_idx      ON apiato.instance (host_id);
CREATE INDEX instance_master_idx    ON apiato.instance (master_instance_id);
CREATE INDEX instance_slave_idx     ON apiato.instance (slave_instance_id);
CREATE INDEX instance_type_idx      ON apiato.instance (instance_type_id);
CREATE INDEX instance_cluster_idx   ON apiato.cluster  (cluster_id);


-- INSTANCE_ATTRIBUTES
CREATE TABLE apiato.instance_attribute (
  attribute_id serial,
  instance_id  integer NOT NULL,
  name         varchar(32) NOT NULL,
  value        varchar(250) NOT NULL,
  CONSTRAINT instance_attribute_pkey        PRIMARY KEY (attribute_id),
  CONSTRAINT instance_attribute_instance_fk FOREIGN KEY (instance_id) REFERENCES apiato.instance (instance_id),
  UNIQUE (instance_id, name)
);
CREATE INDEX instance_attribute_instance_idx ON apiato.instance_attribute (instance_id);



-- CLUSTER_ATTRIBUTES
CREATE TABLE apiato.cluster_attribute (
  attribute_id serial,
  cluster_id   integer NOT NULL,
  name         varchar(32) NOT NULL,
  value        varchar(250) NOT NULL,
  CONSTRAINT cluster_attribute_pkey        PRIMARY KEY (attribute_id),
  CONSTRAINT cluster_attribute_cluster_fk FOREIGN KEY (cluster_id) REFERENCES apiato.cluster (cluster_id),
  UNIQUE (cluster_id, name)
);
CREATE INDEX cluster_attribute_cluster_idx ON apiato.cluster_attribute (cluster_id);

-- JOBS
CREATE TABLE apiato.job (
    job_id          serial,
    instance_id     int NOT NULL,
    name            varchar(64) NOT NULL,
    creation_date   date NOT NULL,
    completion_date date,
    requester       varchar(32) NOT NULL,
    admin_action    int NOT NULL,
    state           apiato.job_state NOT NULL,
    log             text,
    result          varchar(2048),
    email_sent      date,
    CONSTRAINT job_pkey        PRIMARY KEY (job_id),
    CONSTRAINT job_instance_fk FOREIGN KEY (instance_id) REFERENCES apiato.instance (instance_id)

);
CREATE INDEX job_instance_idx ON apiato.job (instance_id);


-- VOLUME
CREATE TABLE apiato.volume (
    volume_id       serial,
    instance_id     integer NOT NULL,
    volume_type_id  int NOT NULL,
    server        varchar(63) NOT NULL,
    mounting_path varchar(256) NOT NULL,
    CONSTRAINT volume_pkey           PRIMARY KEY (volume_id),
    CONSTRAINT volume_instance_fk    FOREIGN KEY (instance_id)    REFERENCES apiato.instance (instance_id),
    CONSTRAINT volume_volume_type_fk FOREIGN KEY (volume_type_id) REFERENCES apiato.volume_type (volume_type_id)
);
CREATE INDEX volume_instance_idx    ON apiato.volume (instance_id);
CREATE INDEX volume_volume_type_idx ON apiato.volume (volume_type_id);


-- VOLUME_ATTRIBUTE
CREATE TABLE apiato.volume_attribute (
  attribute_id serial,
  volume_id    integer NOT NULL,
  name         varchar(32) NOT NULL,
  value        varchar(250) NOT NULL,
  CONSTRAINT volume_attribute_pkey       PRIMARY KEY (attribute_id),
  CONSTRAINT volume_attribute_volume_fk  FOREIGN KEY (volume_id) REFERENCES apiato.volume (volume_id),
  UNIQUE (volume_id, name)
);
CREATE INDEX volume_attribute_volume_idx ON apiato.volume_attribute (volume_id);


------------------------------
-- FUNCTIONS
------------------------------

-- Get hosts function
CREATE OR REPLACE FUNCTION apiato.get_hosts(host_ids INTEGER[])
RETURNS VARCHAR[] AS $$
DECLARE
  hosts VARCHAR := '';
BEGIN
  SELECT ARRAY (SELECT name FROM host WHERE host_id = ANY(host_ids)) INTO hosts;
  RETURN hosts;
END
$$ LANGUAGE plpgsql;


-- Get volumes function
CREATE OR REPLACE FUNCTION apiato.get_volumes(pid INTEGER)
RETURNS JSON[] AS $$
DECLARE
  volumes JSON[];
BEGIN
  SELECT ARRAY (SELECT row_to_json(t) FROM (SELECT * FROM apiato.volume WHERE instance_id = pid) t) INTO volumes;
  return volumes;
END
$$ LANGUAGE plpgsql;

-- Get instance attribute function
CREATE OR REPLACE FUNCTION apiato.get_instance_attribute(attr_name VARCHAR, inst_id INTEGER)
RETURNS VARCHAR AS $$
DECLARE
  res VARCHAR;
BEGIN
  SELECT value FROM apiato.instance_attribute A WHERE A.instance_id = inst_id AND A.name = attr_name INTO res;
  return res;
END
$$ LANGUAGE plpgsql;

-- Get instance attribute function
CREATE OR REPLACE FUNCTION apiato.get_volume_attribute(attr_name VARCHAR, vol_id INTEGER)
  RETURNS VARCHAR AS $$
DECLARE
  res VARCHAR;
BEGIN
  SELECT value FROM apiato.volume_attribute A WHERE A.instance_id = vol_id AND A.name = attr_name INTO res;
  return res;
END
$$ LANGUAGE plpgsql;

-- Get instance attribute function
CREATE OR REPLACE FUNCTION apiato.get_cluster_attribute(attr_name VARCHAR, clus_id INTEGER)
  RETURNS VARCHAR AS $$
DECLARE
  res VARCHAR;
BEGIN
  SELECT value FROM apiato.cluster_attribute A WHERE A.cluster_id = clus_id AND A.name = attr_name INTO res;
  return res;
END
$$ LANGUAGE plpgsql;

-- Get attributes function
CREATE OR REPLACE FUNCTION apiato.get_instance_attributes(inst_id INTEGER)
  RETURNS JSON AS $$
DECLARE
  attributes JSON;
BEGIN
  SELECT json_object(j.body::text[]) FROM
    (SELECT '{' || string_agg( buf, ',' ) || '}' body
     FROM
       (SELECT  name::text || ', ' || value::text buf
        FROM apiato.instance_attribute
        WHERE instance_id = inst_id) t) j INTO attributes;
  return attributes;
END
$$ LANGUAGE plpgsql;

-- Get attributes function
CREATE OR REPLACE FUNCTION apiato.get_volume_attributes(vol_id INTEGER)
  RETURNS JSON AS $$
DECLARE
  attributes JSON;
BEGIN
  SELECT json_object(j.body::text[]) FROM
    (SELECT '{' || string_agg( buf, ',' ) || '}' body
     FROM
       (SELECT  name::text || ', ' || value::text buf
        FROM apiato.volume_attribute
        WHERE instance_id = vol_id) t) j INTO attributes;
  return attributes;
END
$$ LANGUAGE plpgsql;

-- Get attributes function
CREATE OR REPLACE FUNCTION apiato.get_cluster_attributes(clus_id INTEGER)
  RETURNS JSON AS $$
DECLARE
  attributes JSON;
BEGIN
  SELECT json_object(j.body::text[]) FROM
    (SELECT '{' || string_agg( buf, ',' ) || '}' body
     FROM
       (SELECT  name::text || ', ' || value::text buf
        FROM apiato.cluster_attribute
        WHERE cluster_id = clus_id) t) j INTO attributes;
  return attributes;
END
$$ LANGUAGE plpgsql;

-- Get attributes function
CREATE OR REPLACE FUNCTION apiato.get_cluster_instances(clus_id INTEGER)
RETURNS JSON[] AS $$
DECLARE
  instances JSON[];
BEGIN
  SELECT ARRAY (SELECT row_to_json(t) FROM (SELECT * FROM apiato_ro.metadata WHERE cluster_id = clus_id) t) INTO instances;
  return instances;
END
$$ LANGUAGE plpgsql;


------------------------------
-- VIEWS
------------------------------

-- Instance View
CREATE OR REPLACE VIEW apiato_ro.instance AS
SELECT instance.instance_id AS id,
       instance.owner AS username,
       instance.name,
       instance.e_group,
       instance.category "class",
       instance.creation_date,
       instance.expiry_date,
       instance_type.type AS type,
       instance.project,
       instance.description,
       instance_master.name AS master,
       instance_slave.name AS slave,
       host.name AS host,
       instance.state,
       instance.status
FROM apiato.instance
  LEFT JOIN apiato.instance AS instance_master ON apiato.instance.instance_id = instance_master.instance_id
  LEFT JOIN apiato.instance AS instance_slave ON apiato.instance.instance_id = instance_slave.instance_id
  JOIN apiato.instance_type ON apiato.instance.instance_type_id = apiato.instance_type.instance_type_id
  JOIN apiato.host ON apiato.instance.host_id = apiato.host.host_id;

-- Instance Attribute View
CREATE OR REPLACE VIEW apiato_ro.instance_attribute AS
SELECT instance_attribute.attribute_id AS id,
       instance_attribute.instance_id,
       instance_attribute.name,
       instance_attribute.value
FROM apiato.instance_attribute;

--Volume Attribute View
CREATE OR REPLACE VIEW apiato_ro.volume_attribute AS
SELECT volume_attribute.attribute_id AS id,
       volume_attribute.volume_id,
       volume_attribute.name,
       volume_attribute.value
FROM apiato.volume_attribute;

-- Volume View
CREATE OR REPLACE VIEW apiato_ro.volume AS
SELECT volume.volume_id AS id,
       volume.instance_id,
       apiato.volume_type.type AS type,
       volume.server,
       volume.mounting_path
FROM apiato.volume
  JOIN apiato.volume_type ON apiato.volume.volume_type_id = apiato.volume_type.volume_type_id;

-- Metadata View
CREATE OR REPLACE VIEW apiato_ro.metadata AS
  SELECT
    instance.instance_id AS id,
    instance.owner AS username,
    instance.name AS db_name,
    instance.category "class",
    instance_type.type AS type,
    instance.version,
    string_to_array(host.name::text, ','::text) as hosts,
    apiato.get_instance_attributes(apiato.instance.instance_id) attributes,
    apiato.get_instance_attribute('port', apiato.instance.instance_id ) port,
    get_volumes volumes,
    instance.cluster_id
  FROM apiato.instance
    JOIN apiato.instance_type ON apiato.instance.instance_type_id = apiato.instance_type.instance_type_id
    LEFT JOIN apiato.host ON apiato.instance.host_id = apiato.host.host_id,
    apiato.get_volumes(apiato.instance.instance_id);


-- Metadata View
CREATE OR REPLACE VIEW apiato_ro.cluster AS
  SELECT
    cluster.cluster_id AS id,
    cluster.owner AS username,
    cluster.name AS name,
    cluster.category "class",
    instance_type.type AS type,
    cluster.version,
    get_cluster_instances as instances,
    apiato.get_cluster_attributes(apiato.cluster.cluster_id) as attributes,
    apiato.get_cluster_attribute('port', apiato.cluster.cluster_id ) port
  FROM apiato.cluster
    JOIN apiato.instance_type ON apiato.cluster.instance_type_id = apiato.instance_type.instance_type_id,
    apiato.get_cluster_instances(apiato.cluster.cluster_id);


INSERT INTO apiato.instance_type (type, description)
    VALUES ('zookeeper','zookeeper instance type');

INSERT INTO apiato.host (name, memory)
    VALUES ('host01','2'),
           ('host02','2');

INSERT INTO apiato.cluster (owner, name, category, creation_date, instance_type_id, state, status)
  VALUES ('zookeeper','cluster01','DEV',CURRENT_TIMESTAMP, 1,'RUNNING','ACTIVE');


INSERT INTO apiato.instance (owner, name, category, creation_date, instance_type_id, host_id, state, status, cluster_id)
  VALUES ('zookeeper','node01','DEV',CURRENT_TIMESTAMP, 1, 1,'RUNNING','ACTIVE',1),
         ('zookeeper','node02','DEV',CURRENT_TIMESTAMP, 1, 1,'RUNNING','ACTIVE',1);

INSERT INTO apiato.cluster_attribute (cluster_id, name, value)
    VALUES (1,'service','service01'),
           (1,'user','user01');