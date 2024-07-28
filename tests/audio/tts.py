from google.cloud import texttospeech


def synthesize_long_audio(text, output_file, credentials_path=None, project_id=None, location=None):
    """Synthesizes long-form speech from text and saves it to a local file.

    Args:
        text: The text to be converted to speech.
        output_file: Path to the local file where the audio will be saved.
        credentials_path: (Optional) Path to the Google Cloud service account JSON credentials file.
        project_id: (Optional) Your Google Cloud project ID. If not provided, will attempt to infer from environment.
        location: (Optional) Location of the Text-to-Speech API (e.g., "us-central1"). If not provided, will attempt to infer from environment.
    """

    client = texttospeech.TextToSpeechLongAudioSynthesizeClient(credentials=credentials_path)

    if not project_id:
        try:
            import google.auth

            _, project_id = google.auth.default()
        except ImportError:
            raise ValueError("Project ID not provided and could not be inferred from environment.")

    if not location:
        location = "us-central1"

    parent = f"projects/{project_id}/locations/{location}"

    # Prepare input
    input_text = texttospeech.SynthesisInput(text=text)

    # Voice selection (this example uses a standard US English voice)
    voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Journey-D")

    # Audio configuration (linear16 encoding for raw audio data)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    # Create the request (notice no output_gcs_uri)
    request = texttospeech.SynthesizeLongAudioRequest(
        parent=parent,
        input=input_text,
        audio_config=audio_config,
        voice=voice,
    )

    # Start the long-running operation
    operation = client.synthesize_long_audio(request=request)

    # Wait for the operation to complete
    response = operation.result(timeout=600)  # Adjust timeout as needed

    # Save the audio content to the local file
    with open(output_file, "wb") as out:
        out.write(response.audio_content)

    print(f"Long audio synthesis finished. Audio saved to: {output_file}")


# Example usage
if __name__ == "__main__":
    # with open("your_long_text_file.txt", "r") as file:
    #     long_text = file.read()

    long_text = r"""
    Defining Terms.
    Business
    An organization engaged in the trade of goods, services, or both, with the primary aim of generating profit.
    Venture
    A new business undertaking characterized by risk and the potential for significant returns.
    Entrepreneurship
    The process of creating, developing, and managing a new business venture while bearing the majority of its risks in the pursuit of profit.
    Startup
    A young company designed to rapidly develop and validate a scalable business model.
    Company
    A legal entity formed by individuals, shareholders, or stockholders with the purpose of operating a for-profit or non-profit enterprise.
    Key Point:
    •	Overlaps: There's overlap between these terms; new startups are often considered business ventures, and entrepreneurship is how many startups are born.
    Three Dimensions of a Business
    •	Commerce: This refers to the production, exchange, and trade of goods and services. It’s the economic aspect of a business.
    •	Occupation: This is about the skills and abilities people acquire to create valuable goods and services. It’s the professional aspect of a business.
    •	Organization: This involves coordinating and controlling tasks and authority relationships to achieve a common goal, typically profits. It’s the structural aspect of a business.
    In simpler terms, a business is a place where goods and services are made and sold (commerce), by people with certain skills (occupation), working together in a structured way (organization) to make profits.
    Business as a System
    What is a Business System?
    A business system is a combination of commerce, occupations, and organizations that work together to produce and distribute goods and services, creating value for society.
    Creating Value: To create value, a business needs three key components: sensors, facilitators, and generators.
    •	Sensors: These are systems like accounting and information systems that collect and analyze data to guide business decisions.
    •	Facilitators: These are elements like distribution channels and supply chains that help deliver the business’s products or services to the market.
    •	Generators: This involves understanding the end-consumer (consumer behavior) to create products or services that meet their needs and preferences.
    The Evolution of Business
    •	Barter System: This was the earliest form of trade where goods and services were exchanged directly for other goods and services without using a medium of exchange, like money.
    •	Use of Money: With the introduction of money, trade became more efficient as it provided a common measure of value and made transactions simpler.
    •	Industrial Revolution (Mass Production): This period marked a shift from handmade goods to machine-made goods, leading to mass production. It significantly increased the scale and efficiency of businesses.
    •	Information Technology (IT) Era: The advent of computers and the internet revolutionized business operations, enabling faster communication, better data management, and more efficient processes.
    •	Knowledge-Based Era: In this era, knowledge and information became key business assets. Businesses that could effectively manage and utilize knowledge gained a competitive advantage.
    •	Artificial Intelligence (AI) Based Era: We are currently in the AI era, where businesses are leveraging AI technologies to automate processes, make data-driven decisions, and provide personalized customer experiences.
    Understanding Business as a Game and a System of Cooperation
    The Game of Business
    In the business world, there are no set rules that guarantee everyone will profit or profit equally. The distribution of profit isn’t predetermined and can vary widely. Success in this “game” largely depends on one’s ability to effectively participate and navigate the complexities of business.
    Business: A Game or Cooperation?
    This question highlights the dual nature of business. On the one hand, it’s like a game with competition and strategy. On the other hand, it’s about cooperation and co-existence, as businesses often need to work together for mutual benefit.
    Capital
    Different Perspectives
    •	Financial/Accounting Perspective: Capital is the total assets accumulated by a business for generating income.
    •	Economic Perspective: From an economic viewpoint, capital is anything that provides value or benefit to its owner, such as the entrepreneur. It includes the risk of the business and ownership rights.
    •	Investor Perspective: For investors, capital is a measure of wealth and resources that can increase wealth through investments. It’s what is invested in a business to generate returns.
    •	Business Perspective: In business terms, capital includes everything that is used in the process of transforming inputs into desired outputs or outcomes.
    Types of Capital in Business
    •	Physical Capital: These are tangible assets that contribute to wealth creation. Examples include production plants and machinery.
    •	Financial Capital: This refers to money that is typically traded or invested in monetary markets. An example is an investment portfolio.
    •	Social Capital: This represents the value that relationships bring to businesses. Examples include brand equity, supply chain relationships, and strategic alliances.
    •	Intellectual Capital (IC): This is the collective knowledge of individuals in an organization or society. Examples include the key talents in a business, such as product designers and engineers in the IT industry. IC is now considered a true capital cost, similar to investments in machinery and plants. Expenses incurred in employee training (to maintain the value of intellectual assets) are equivalent to the depreciation costs of physical assets.
    Basic Forms of Intellectual Capital
    •	Human Capital (HC): Human capital represents the combined knowledge, skills, experiences, and abilities of an organization's workforce. 
    This is the organization’s constantly renewable source of creativity and innovativeness, although it is not reflected in financial statements. Examples include motivation, satisfaction, productivity, innovation, and skills.
    •	Customer Capital: This is the value of relationships that a firm builds with its customers. Examples include customer loyalty to the firm and/or its products, and customer lifetime value.
    •	Structural Capital (SC): This does not reside in the heads of employees but remains with the organization even when employees leave. SC results from products or systems the firm created over time. Examples include competitive intelligence, formulas, information systems, patents, policies, and processes.
    Equity Capital vs Debt Capital
    •	Debt Capital: This refers to funds that a business borrows and must repay at a later date, with interest. The cost of debt capital is the interest rate, which must be paid regardless of the company’s profit margins. 
    For example, if a company borrows Rs. 550,000 from a bank at a 7% interest rate, the cost of capital is the 7% interest. However, the actual cost of capital may be lower when corporate taxes are deducted.
    •	Equity Capital: This refers to funds that shareholders have invested in the business. While there’s no legal obligation to repay these funds, shareholders do expect a return on their investment. This can come in the form of increased stock valuations or dividends. The risk to shareholders is greater than to lenders of debt capital because if the business fails, shareholders may lose their entire investment.
    Remember, in the secondary market, ownerships (shares) are transferred, and even competitors may buy these shares.
    Capital Structure: Collection and Allocation
    Collection
    This refers to the decision-making process regarding the composition of capital between Equity and Debt capital. Factors to consider include:
    •	Risk Assessments: This involves evaluating the risk of ownership, Board of Directors (BoD), and voting rights.
    •	Cost of Capital: If a business holds a large amount of liquid capital, it could incur a high opportunity cost, which is the potential investment income that could have been earned if the funds were invested elsewhere.
    •	Control and Ownership: This involves weighing the risk of bearing a business against the potential for high capital returns.
    Allocation
    This refers to how the collected capital is distributed across the business’s assets. This could include allocations for subsidiaries, plants, business units, employee training in the IT industry, and software updates. Factors to consider include:
    •	Business Priorities: The allocation should align with the business’s priorities for the year.
    •	Strategic Plan: The allocation should also align with the business’s long-term strategic plan.
    Funding Options for Startup Companies
    •	Personal Investment/Self-Funding/Bootstrapping: This involves using personal money or assets to fund the business. Investors appreciate it when owners show commitment and are willing to take a risk.
    •	Love Money: This is money loaned or invested by family or friends to help start the business.
    •	Grants: These are funds given by government organizations under certain conditions. If the business meets the terms of the grant, it doesn’t have to repay the money.
    •	Angel Investors: These are typically wealthy individuals who invest directly in small businesses. They usually make small investments and offer their experience, networks, and knowledge to help startups succeed.
    •	Loans: While it’s not easy for startups to obtain bank loans, there are government programs that guarantee business loans from financial institutions. There are also organizations that specialize in lending to new ventures.
    •	Venture Capital: Venture capitalists invest in promising startups in high-growth, technology-driven sectors. They take an ownership stake in companies to finance the high-risk early stages of development. They typically invest more than angel investors and expect a substantial return.
    Venture Capital Explained
    •	What is Venture Capital?: Venture capital is a type of financial capital provided by investors to small businesses that show high long-term potential. It’s a form of private equity, which includes stocks (shares) and debts of private companies, i.e., firms not listed on a stock exchange.
    •	Why is it Important?: Venture capital is a primary source of funding for startups, especially those without access to capital markets, unable to secure a bank loan, or complete a debt offering. Startups need capital for various purposes such as growth, developing new products, or entering new markets.
    •	Who Provides Venture Capital?: Most venture capital comes from a group of wealthy investors, investment banks, or other financial institutions.
    •	Beyond Financial Funding: Venture capital is not limited to just financial funding. Venture capitalists often provide managerial and technical expertise to startups, helping them navigate the early stages of their business.
    Assets and Liabilities
    Assets
    Assets are resources owned or controlled by a business that are expected to provide future benefits.
    Characteristics of an Asset
    •	Economic Value: Assets have an economic value to the business.
    •	Ownership or Control: The business owns or has the right to access the asset.
    •	Convertibility: Assets can be converted into cash.
    •	Disposal Value: Disposing of the asset can bring money to the organization.
    Liquidity of Assets
    Liquidity refers to how quickly an asset can be converted into cash without affecting its market price.
    Classification of Assets
    •	Current Assets: These are assets that can be converted into cash within one year.
    Examples include cash and cash equivalents (like treasury bills and certificates of deposit), marketable securities (liquid debt securities or equity), accounts receivables, and inventory (goods available for sale or raw materials).
    •	Long-Term Assets: These are assets that cannot be converted into cash within one year. Examples include buildings and machinery.
    •	Financial Assets: These represent investments in the assets and securities of other businesses.
    •	Intangible Assets: These are non-physical assets that have value. Examples include patents, copyrights, and brand names.
    The proportion between current and fixed (long-term) assets will vary from business to business, depending on factors like:
    •	Nature of the Business: For example, IT businesses may have more intangible assets, while manufacturing businesses may have more fixed assets (like machinery).
    •	Future Orientation of the Business: This could influence the ratio between long-term and short-term assets.
    •	Priorities of the Business: The strategic plan of the business will also play a role in asset allocation.
    Liabilities
    Liabilities are financial obligations that a business needs to settle in the future due to past transactions or events. They represent a sacrifice of future economic value to settle past obligations.
    •	Future Obligations: Liabilities are obligations that need to be settled in the future. They arise from past activities or transactions.
    •	Legally Binding: Liabilities are legally binding, meaning the business is legally obligated to settle them.
    •	Result of Acquisition: In most cases, liabilities arise as a result of acquiring something that brings economic value to the business.
    •	Reduction of Assets: Settling liabilities often results in a reduction of assets, as assets may need to be used or sold to settle the liabilities.
    Equity
    The aggregate difference between assets and liabilities is known as equity. This represents the net residual ownership of the owners in a business.
    Profit
    Profit is the positive gain generated from business operations or investment after subtracting all expenses or costs. It’s the financial return or reward that entrepreneurs aim for.
    Profit can have different meanings for various stakeholders such as businessmen, accountants, policymakers, workers, and economists.
    •	Results of Business Decisions: Profit is the financial outcome of business decisions. It’s the result of strategic planning, operational efficiency, and effective management.
    •	Fuel for the Business: Profit serves as the financial fuel for a business. It enables growth, expansion, and reinvestment in the business.
    •	Measurement of Success: Profit is often used as a key indicator to measure the success of a business. A profitable business is generally considered successful.
    •	Return for Risk: Profit is the return entrepreneurs aim to achieve to reflect the risk they took in starting and running the business.
    •	Motivator/Stimulator: Profit serves as a motivator and stimulator. It incentivizes business owners to take risks and make investments.
    Different Types of Profits
    •	Economic Profit: This is calculated as total revenue minus both explicit and implicit costs. Explicit costs are direct out-of-pocket expenses for running the business, while implicit costs are the opportunity costs of using resources that the business already owns.
    •	Accounting Profit: This is calculated as total revenue minus explicit costs. It’s the profit figure that businesses typically report on their financial statements.
    •	Gross Profit: This is calculated as sales minus the cost of sales (the direct costs attributable to the production of the goods sold in a company). It represents the profit a company makes after deducting the costs associated with making and selling its products.
    •	Operating Profit: This is calculated as gross profit minus operating expenses. Operating expenses are the costs associated with running the business’s core operations.
    •	Net Profit: This is the income left over after all expenses, including taxes and interest, have been deducted. It’s often referred to as the “bottom line” because it’s usually the last line on a company’s income statement.
    Profits as a Signal
    Profit is an important indicator of a business’s financial health, but it should not be considered in isolation. Here are some key points to consider:
    •	Comparative Analysis: Profits should be compared against other time periods and industry competitors. This benchmarking process can provide a more accurate picture of the business’s performance.
    •	Varying Meanings: Profit can signify various things, such as effective management by the Board of Directors (BoD), an increasing customer base, and more. High profits don’t always mean a business is doing well. Other factors need to be considered.
    Best Measure of a Company’s Financial Health
    There isn’t a one-size-fits-all answer to this. The best measure of a company’s financial health depends on the priorities and strategic vision of the business. Different businesses might focus on different indicators based on their goals, industry norms, and specific challenges.
    Profits vs Return
    •	Nature of Income: Profit is considered residual income, which means it’s the income that remains after all costs and expenses have been deducted from the total revenue. On the other hand, return refers to the total revenue generated from an investment or business activity.
    •	Positive or Negative Values: Profits can be negative if the costs and expenses exceed the total revenue, indicating a loss. However, returns are always positive as they represent the total revenue or gains from an investment or business activity, regardless of costs or expenses.
    •	Fluctuations: Profits tend to fluctuate more than returns. This is because profits are influenced by various factors such as costs, expenses, and market conditions, while returns are simply the total revenue or gains, which are generally more stable.

    """

    output_file = "output.wav"  # Change file extension if you want a different format
    synthesize_long_audio(long_text, output_file)
