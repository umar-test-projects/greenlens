import {defineConfig} from 'vite';

export default defineConfig({
 server: {
  allowedHosts: ['yellow-lies-battle.loca.lt', 'hungry-masks-strive.loca.lt'],
  proxy: {'/query': {target:'http://127.0.0.1:3001',changeOrigin:true},
          '/satellite': {target:'http://127.0.0.1:3001',changeOrigin:true}},
 },
});
