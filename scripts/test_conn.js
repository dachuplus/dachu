import pg from 'pg';
const { Client } = pg;

const configs = [
  { port: 6543, user: 'postgres.tqhtegazxykkqfcpejky', label: 'Tx pooler 6543 project user' },
  { port: 6543, user: 'postgres', label: 'Tx pooler 6543 postgres' },
  { port: 5432, user: 'postgres', label: 'Session pooler 5432 postgres' },
];

(async () => {
  for (const cfg of configs) {
    const client = new Client({
      host: 'aws-0-ap-southeast-1.pooler.supabase.com',
      port: cfg.port,
      database: 'postgres',
      user: cfg.user,
      password: 'Mao15901622389!',
      ssl: { rejectUnauthorized: false }
    });
    try {
      await client.connect();
      await client.query('SELECT 1 as ok');
      console.log(cfg.label + ': OK');
      await client.end();
      break;
    } catch (err) {
      console.log(cfg.label + ':', err.code || '', err.message.split('\n')[0]);
    }
  }
})();
