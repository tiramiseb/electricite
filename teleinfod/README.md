teleinfod
=========

Installation
------------

To pseudo-manually install on a system using systemd, use the
`install_systemd.sh` script.

Configuration
-------------

The default configuration file is `/usr/local/etc/teleinfod.conf`.

All parameters are mandatory.

MySQL tables
------------

When the "mysql" output is activated, data is stored in two MySQL tables.

Create the DB and a user:

    CREATE DATABASE teleinfo CHARACTER SET utf8;
    CREATE USER 'teleinfo'@'ip_address' IDENTIFIED BY 'password';
    GRANT SELECT, INSERT on teleinfo.* TO 'teleinfo'@'ip_address';

Here is the SQL command to create the tables:

    CREATE TABLE teleinfo_periodic_amperage (
      datetime DATETIME NOT NULL PRIMARY KEY,
      tarif CHAR(4),               /* OPTARIF */
      subscribed_amperage SMALLINT, /* ISOUSC */
      min_amperage SMALLINT,        /* IINST */
      avg_amperage SMALLINT,
      max_amperage SMALLINT,
      period CHAR(4),               /* PTEC */
      tomorrow CHAR(4)              /* DEMAIN (only with the "tempo" option) */
    );
    
    CREATE TABLE teleinfo_hourly_counters (
      datetime DATETIME NOT NULL PRIMARY KEY,
      tarif CHAR(4),       /* OPTARIF */
      /* Base */
      base INT UNSIGNED,
      # HC */
      hchc INT UNSIGNED,
      hchp INT UNSIGNED,
      /* Tempo */
      bbrhcjb INT UNSIGNED,
      bbrhpjb INT UNSIGNED,
      bbrhcjw INT UNSIGNED,
      bbrhpjw INT UNSIGNED,
      bbrhcjr INT UNSIGNED,
      bbrhpjr INT UNSIGNED,
      /* EJP */
      ejphn INT UNSIGNED,
      ejphpm INT UNSIGNED
    );
