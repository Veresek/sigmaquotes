import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
	plugins: [
		react({
			babel: {
				plugins: [['babel-plugin-react-compiler']],
			},
		}),
	],
	server: {
		port: 3000,
		allowedHosts: [
			'localhost',
			'0.0.0.0',
			'sigmaquotes.pl',
			'www.sigmaquotes.pl',
		],
	},
});
