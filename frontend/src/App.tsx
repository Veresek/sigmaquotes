import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import "./App.css";

interface Quote {
	id: number;
	author: string;
	content: string;
}

function App() {
	const [quotes, setQuotes] = useState<Quote[]>([]);

	useEffect(() => {
		const fetchQuotes = async () => {
			try {
				const res = await fetch(`/api/quotes`);
				const data = await res.json();
				setQuotes(data);
			} catch (error) {
				console.error("Error fetching quotes:", error);
			}
		};
		fetchQuotes();
	}, []);

	return (
		<div className="container">
			<header>
				<h1 className="title">SIGMA QUOTES</h1>
				<p className="subtitle">
					Sigmastyczne cytaty z sigmastycznego discorda
				</p>
				<nav>
					<Link
						to="/manifesto"
						className="nav-link"
						style={{
							color: "white",
							textDecoration: "underline",
							marginTop: "10px",
							display: "inline-block",
						}}>
						Przeczytaj manifest cwela
					</Link>
				</nav>
			</header>

			<main>
				<section className="quotes-list">
					{quotes.map(quote => (
						<div key={quote.id} className="quote-card">
							<p className="quote-content">"{quote.content}"</p>
						</div>
					))}
					{quotes.length == 0 && <p className="no-quotes">Brak cytatów.</p>}
				</section>
			</main>
		</div>
	);
}

export default App;
